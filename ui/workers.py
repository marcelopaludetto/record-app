"""
Workers para operações pesadas sem bloquear a UI.
"""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from config import (
    WHISPER_LANGUAGE, GROQ_API_KEY, GROQ_WHISPER_MODEL,
    TRANSCRIPTIONS_DIR, WHISPER_PROMPT,
)
from core.recorder import source_audio_path
from core.transcriber import TranscriptionSegment, Transcriber
from core.meeting_controller import MeetingController

_PYTHON = str(Path(sys.executable).parent / "python.exe")
_TRANSCRIBE_GROQ = str(Path(__file__).parent.parent / "core" / "transcribe_groq.py")


class TxtProcessingWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, controller: MeetingController):
        super().__init__()
        self._controller = controller

    def run(self):
        try:
            self.progress.emit("Gerando resumo...", 20)
            self._controller.summarize_current()
            self.progress.emit("Exportando documento...", 80)
            path = self._controller.export_current()
            self.progress.emit("Documento salvo!", 100)
            self.finished.emit(str(path))
        except Exception as exc:
            import traceback
            self.error.emit(f"{exc}\n\n{traceback.format_exc()}")


class ProcessingWorker(QThread):
    progress = pyqtSignal(str, int)   # (mensagem, percentual 0-100)
    finished = pyqtSignal(str)        # caminho do .md gerado
    error = pyqtSignal(str)

    def __init__(self, controller: MeetingController):
        super().__init__()
        self._controller = controller

    def run(self):
        try:
            meeting = self._controller.current_meeting()
            if not meeting or not meeting.audio_path:
                self.error.emit("Nenhum áudio disponível para transcrever.")
                return

            clean_env = os.environ.copy()
            clean_env["PYTHONPATH"] = ""
            clean_env["PYTHONIOENCODING"] = "utf-8"
            clean_env["PYTHONUTF8"] = "1"
            clean_env["GROQ_API_KEY"] = GROQ_API_KEY

            inputs = self._transcription_inputs(meeting.audio_path)
            segments: list[TranscriptionSegment] = []
            progress_span = max(1, 50 // len(inputs))

            for index, (speaker, audio_path) in enumerate(inputs):
                progress_start = 10 + index * progress_span
                segments.extend(
                    self._transcribe_audio(
                        audio_path=audio_path,
                        speaker=speaker,
                        clean_env=clean_env,
                        progress_start=progress_start,
                        progress_span=progress_span,
                    )
                )

            segments.sort(key=lambda s: (s.start, s.end))

            # ----------------------------------------------------------
            # Salva transcrição no meeting atual via controller
            # ----------------------------------------------------------
            transcriber = Transcriber()
            transcript_text = transcriber.segments_to_text(segments)

            meeting.transcript_text = transcript_text
            meeting.whisper_model = GROQ_WHISPER_MODEL

            from core.meeting_controller import _safe_name
            safe = _safe_name(meeting.title)
            date_str = meeting.started_at.strftime("%Y-%m-%d_%H-%M")
            txt_path = TRANSCRIPTIONS_DIR / f"{date_str}_{safe}.txt"
            txt_path.write_text(transcript_text, encoding="utf-8")
            meeting.transcript_path = txt_path
            meeting.status = "summarizing"

            self.progress.emit(
                f"Transcrição concluída ({len(segments)} segmentos). Gerando resumo...",
                65,
            )

            # ----------------------------------------------------------
            # Sumarização
            # ----------------------------------------------------------
            self._controller.summarize_current()
            self.progress.emit("Resumo gerado. Exportando documento...", 90)

            # ----------------------------------------------------------
            # Exportação
            # ----------------------------------------------------------
            path = self._controller.export_current()
            self.progress.emit("Documento salvo!", 100)
            self.finished.emit(str(path))

        except Exception as exc:
            import traceback
            self.error.emit(f"{exc}\n\n{traceback.format_exc()}")

    def _transcription_inputs(self, audio_path: Path) -> list[tuple[str, Path]]:
        mic_path = source_audio_path(audio_path, "mic")
        system_path = source_audio_path(audio_path, "system")

        inputs: list[tuple[str, Path]] = []
        if mic_path.exists():
            inputs.append(("mic", mic_path))
        if system_path.exists():
            inputs.append(("system", system_path))

        if inputs:
            return inputs
        return [("", audio_path)]

    def _transcribe_audio(
        self,
        audio_path: Path,
        speaker: str,
        clean_env: dict[str, str],
        progress_start: int,
        progress_span: int,
    ) -> list[TranscriptionSegment]:
        label = _progress_label(speaker)
        self.progress.emit(f"Transcrevendo {label}...", progress_start)

        cmd = [
            _PYTHON,
            _TRANSCRIBE_GROQ,
            str(audio_path),
            GROQ_WHISPER_MODEL,
            WHISPER_LANGUAGE,
            WHISPER_PROMPT,
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=clean_env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        stderr_lines: list[str] = []

        def _read_stderr():
            if proc.stderr is None:
                return
            for raw_line in proc.stderr:
                line = raw_line.decode("utf-8", errors="replace").strip()
                stderr_lines.append(line)
                if line.startswith("PROGRESS:"):
                    try:
                        pct = int(line.split(":")[1])
                        scaled = progress_start + int(pct * progress_span / 100)
                        self.progress.emit(f"Transcrevendo {label}... {pct}%", scaled)
                    except ValueError:
                        pass

        stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
        stderr_thread.start()

        if proc.stdout is None:
            raise RuntimeError("Falha ao capturar saída do transcritor.")
        stdout_bytes = proc.stdout.read()
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr_thread.join()
        proc.wait()

        if proc.returncode != 0:
            err_detail = "\n".join(stderr_lines[-5:])
            raise RuntimeError(
                f"Falha na transcrição de {label} (código {proc.returncode}):\n{err_detail}"
            )

        try:
            raw_segments = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Resultado inválido do transcritor:\n{stdout[:300]}") from exc

        if isinstance(raw_segments, dict) and "error" in raw_segments:
            raise RuntimeError(raw_segments["error"])
        if not isinstance(raw_segments, list):
            raise RuntimeError(f"Resultado inesperado do transcritor:\n{stdout[:300]}")

        return [
            TranscriptionSegment(
                start=s["start"],
                end=s["end"],
                text=s["text"],
                speaker=speaker,
            )
            for s in raw_segments
        ]


def _progress_label(speaker: str) -> str:
    if speaker == "mic":
        return "microfone"
    if speaker == "system":
        return "áudio do sistema"
    return "áudio"
