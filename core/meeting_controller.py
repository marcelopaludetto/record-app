import re
from datetime import datetime
from pathlib import Path

from config import AUDIO_DIR, ANTHROPIC_MODEL, MIC_DEVICE_INDEX, LOOPBACK_DEVICE_INDEX, SUMMARIZER_BACKEND, NOTES_DIR, NAME_ALIASES
from core.recorder import AudioRecorder
from core.summarizer import Summarizer
from core.summarizer_gemini import GeminiSummarizer
from core.exporter import DocumentExporter
from storage.models import Meeting, Topic, Bullet, NextStep
from storage import database


class MeetingController:
    def __init__(self):
        # Recorder inicializado sem loopback — detecção ocorre lazy em start_meeting()
        self._recorder = AudioRecorder(mic_device=MIC_DEVICE_INDEX, loopback_device=None)
        self._loopback_ready = False
        self._summarizer = GeminiSummarizer() if SUMMARIZER_BACKEND == "gemini" else Summarizer()
        self._exporter = DocumentExporter()
        self._current: Meeting | None = None
        database.init_db()

    def set_devices(self, mic_index: int | None, loopback_index: int | None):
        """Permite troca de dispositivos em runtime (ex: tela de configurações)."""
        self._recorder = AudioRecorder(
            mic_device=mic_index,
            loopback_device=loopback_index,
        )
        self._loopback_ready = True

    # ------------------------------------------------------------------
    # Gravação
    # ------------------------------------------------------------------

    def start_meeting(self, title: str):
        if self._current and self._recorder.is_recording:
            raise RuntimeError("Já existe uma reunião em andamento.")
        if not self._loopback_ready:
            loopback_idx = LOOPBACK_DEVICE_INDEX
            if loopback_idx is None:
                default = AudioRecorder.get_default_loopback()
                loopback_idx = default["index"] if default else None
            self._recorder = AudioRecorder(mic_device=MIC_DEVICE_INDEX, loopback_device=loopback_idx)
            self._loopback_ready = True
        self._current = Meeting(title=title, started_at=datetime.now())
        self._recorder.start()

    def import_txt(self, txt_path: Path, title: str):
        """Carrega um .txt ou .vtt de transcrição existente e prepara para sumarização."""
        if self._current and self._recorder.is_recording:
            raise RuntimeError("Já existe uma reunião em andamento.")
        started_at = datetime.now()
        try:
            parts = txt_path.stem.split("_")
            started_at = datetime.strptime(f"{parts[0]}_{parts[1]}", "%Y-%m-%d_%H-%M")
        except (IndexError, ValueError):
            pass
        raw = txt_path.read_text(encoding="utf-8")
        transcript = _parse_vtt(raw) if txt_path.suffix.lower() == ".vtt" else raw
        self._current = Meeting(title=title, started_at=started_at)
        self._current.transcript_text = transcript
        self._current.transcript_path = txt_path
        self._current.ended_at = started_at
        self._current.status = "summarizing"

    def import_audio(self, audio_path: Path, title: str):
        """Carrega um arquivo de áudio existente como reunião atual, sem gravar."""
        if self._current and self._recorder.is_recording:
            raise RuntimeError("Já existe uma reunião em andamento.")
        # Tenta extrair data/hora do nome do arquivo (formato YYYY-MM-DD_HH-MM_*)
        started_at = datetime.now()
        try:
            parts = audio_path.stem.split("_")
            started_at = datetime.strptime(f"{parts[0]}_{parts[1]}", "%Y-%m-%d_%H-%M")
        except (IndexError, ValueError):
            pass
        self._current = Meeting(title=title, started_at=started_at)
        self._current.audio_path = audio_path
        self._current.ended_at = started_at
        self._current.status = "transcribing"

    def stop_recording(self):
        if not self._current:
            raise RuntimeError("Nenhuma reunião em andamento.")
        if not self._recorder.is_recording:
            return

        self._current.ended_at = datetime.now()
        safe = _safe_name(self._current.title)
        date_str = self._current.started_at.strftime("%Y-%m-%d_%H-%M")
        audio_path = AUDIO_DIR / f"{date_str}_{safe}.wav"
        self._recorder.stop(audio_path)
        self._current.audio_path = audio_path
        self._current.status = "transcribing"

    @property
    def recorded_seconds(self) -> float:
        return self._recorder.recorded_seconds

    # ------------------------------------------------------------------
    # Sumarização
    # ------------------------------------------------------------------

    def summarize_current(self):
        if not self._current or not self._current.transcript_text:
            raise RuntimeError("Sem transcrição para sumarizar.")

        plain = _plain_from_transcript(self._current.transcript_text)
        result = self._summarizer.summarize(plain)

        self._current.topics = [
            Topic(
                title=t.get("title", ""),
                bullets=[
                    Bullet(
                        text=b.get("text", ""),
                        sub_bullets=b.get("sub_bullets", []),
                    )
                    for b in t.get("bullets", [])
                ],
            )
            for t in result.get("topics", [])
        ]

        self._current.next_steps = [
            NextStep(action=s.get("action", ""))
            for s in result.get("next_steps", [])
        ]

        self._current.tipo_agenda = result.get("tipo_agenda", "")
        self._current.temas       = result.get("temas", [])
        self._current.tldr        = result.get("tldr", [])
        self._current.entities    = _normalize_entities(result.get("entities", []))

        # Aplica [[wikilinks]] nos campos de texto
        entities = self._current.entities
        if entities:
            self._current.tldr = [_apply_wikilinks(t, entities) for t in self._current.tldr]
            for topic in self._current.topics:
                for bullet in topic.bullets:
                    bullet.text = _apply_wikilinks(bullet.text, entities)
                    bullet.sub_bullets = [_apply_wikilinks(s, entities) for s in bullet.sub_bullets]
            for step in self._current.next_steps:
                step.action = _apply_wikilinks(step.action, entities)

        self._current.ollama_model = ANTHROPIC_MODEL
        self._current.status = "done"

    # ------------------------------------------------------------------
    # Exportação + persistência
    # ------------------------------------------------------------------

    def export_current(self) -> Path:
        if not self._current:
            raise RuntimeError("Nenhuma reunião para exportar.")

        md_path = self._exporter.export_markdown(self._current)
        self._current.output_md_path = md_path

        meeting_id = database.save_meeting(self._current)
        database.delete_meeting(meeting_id)  # .md é a fonte de verdade

        self._current = None
        return md_path

    # ------------------------------------------------------------------
    # Histórico
    # ------------------------------------------------------------------

    def list_meetings(self, limit: int = 100) -> list[Meeting]:
        from storage.markdown_reader import list_md_meetings
        completed = list_md_meetings(NOTES_DIR, limit=limit)
        in_progress = database.list_active_meetings()
        return (in_progress + completed)[:limit]

    def get_meeting(self, meeting_id: int) -> Meeting | None:
        return database.get_meeting(meeting_id)

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    def is_ollama_available(self) -> bool:
        return self._summarizer.is_available()

    def is_recording(self) -> bool:
        return self._recorder.is_recording

    def current_meeting(self) -> Meeting | None:
        return self._current


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _normalize_entities(entities: list[dict]) -> list[dict]:
    """Normaliza nomes das entidades usando NAME_ALIASES, removendo duplicatas."""
    seen: set[str] = set()
    result = []
    for entity in entities:
        canonical = _canonical_name(entity["name"])
        key = canonical.lower()
        if key not in seen:
            seen.add(key)
            result.append({"name": canonical, "type": entity["type"]})
    return result


def _canonical_name(name: str) -> str:
    """Retorna o nome canônico para um dado nome (case-insensitive)."""
    for alias, canonical in NAME_ALIASES.items():
        if alias.lower() == name.lower():
            return canonical
    return name


def _apply_wikilinks(text: str, entities: list[dict]) -> str:
    """Envolve nomes de pessoas e projetos em [[wikilinks]] do Obsidian.
    Para cada entidade, busca também variações definidas em NAME_ALIASES.
    """
    # Mapa reverso: canônico → [aliases que apontam para ele]
    reverse: dict[str, list[str]] = {}
    for alias, canonical in NAME_ALIASES.items():
        reverse.setdefault(canonical, []).append(alias)

    sorted_entities = sorted(entities, key=lambda e: len(e["name"]), reverse=True)
    for entity in sorted_entities:
        canonical = entity["name"]
        # Busca a forma canônica + todas as variações incorretas no texto
        search_terms = sorted(
            [canonical] + reverse.get(canonical, []),
            key=len, reverse=True,
        )
        for term in search_terms:
            pattern = rf'(?<!\[)\b{re.escape(term)}\b(?!\])'
            text = re.sub(pattern, f'[[{canonical}]]', text, flags=re.IGNORECASE)
    return text


def _safe_name(title: str) -> str:
    safe = "".join(c if (c.isalnum() or c in "-_") else "-" for c in title.replace(" ", "-"))
    return safe[:40].strip("-")


def _parse_vtt(text: str) -> str:
    """Extrai texto puro de um arquivo WebVTT, ignorando cabeçalho e timestamps."""
    import re
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if re.match(r"[\d:]+\.?\d*\s+-->\s+[\d:]+", line):
            continue
        lines.append(line)
    return " ".join(lines)


def _plain_from_transcript(text: str) -> str:
    """Remove marcações de timestamp do texto da transcrição."""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "**" in line:
            parts = line.split("**", 2)
            raw = parts[-1].strip() if len(parts) >= 3 else line
        else:
            raw = line
        if raw:
            lines.append(raw)
    return " ".join(lines)
