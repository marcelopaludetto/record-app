"""
Lê arquivos .md exportados para o Obsidian e os converte em objetos Meeting.
Os arquivos .md são a fonte de verdade para reuniões concluídas.
"""
import re
from datetime import datetime, timedelta
from pathlib import Path

from storage.models import Meeting, Topic, Bullet, NextStep

# Padrão de nome de arquivo: YYYY-MM-DD... ou YYYY-MM-DD.md
_DATE_PREFIX = re.compile(r'^\d{4}-\d{2}-\d{2}([ _].+)?$')


def list_md_meetings(notes_dir: Path, limit: int = 100) -> list[Meeting]:
    """Varre notes_dir por arquivos .md com prefixo de data e retorna Meeting's, mais recentes primeiro."""
    if not notes_dir.exists():
        return []

    candidates = [
        p for p in notes_dir.iterdir()
        if p.is_file() and p.suffix == '.md' and _DATE_PREFIX.match(p.stem)
    ]
    candidates.sort(key=lambda p: p.name, reverse=True)

    meetings = []
    for path in candidates[:limit]:
        m = parse_md_file(path)
        if m is not None:
            meetings.append(m)
    return meetings


def parse_md_file(path: Path) -> Meeting | None:
    """Parseia um arquivo .md e retorna um Meeting. Retorna None em erro irrecuperável."""
    try:
        text = path.read_text(encoding="utf-8")
        fm, body = _extract_frontmatter(text)

        title = fm.get("titulo") or _title_from_stem(path.stem)
        m = Meeting(title=title)
        m.id = None
        m.status = "done"
        m.output_md_path = path
        m.transcript_text = ""
        m.audio_path = None
        m.transcript_path = None
        m.tipo_agenda = fm.get("tipo_agenda", "")
        m.temas = fm.get("tags", [])

        # Datas
        m.started_at = _parse_started_at(fm, path.stem)
        m.ended_at = _parse_ended_at(fm, m.started_at)

        # Conteúdo do body
        topics, next_steps, tldr = _parse_body(body)
        m.topics = topics
        m.next_steps = next_steps
        m.tldr = tldr

        return m
    except Exception:
        return None


# ------------------------------------------------------------------
# Frontmatter
# ------------------------------------------------------------------

def _extract_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), None)
    if end is None:
        return {}, text
    fm = _parse_simple_yaml(lines[1:end])
    body = "\n".join(lines[end + 1:])
    return fm, body


def _parse_simple_yaml(lines: list[str]) -> dict:
    result: dict = {}
    current_list_key: str | None = None

    for line in lines:
        # Item de lista
        if line.startswith("  - ") or line.startswith("    - "):
            if current_list_key:
                result[current_list_key].append(line.strip().lstrip("- "))
            continue

        # Par chave: valor
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value == "":
                # Início de lista
                result[key] = []
                current_list_key = key
            else:
                result[key] = value
                current_list_key = None
        else:
            current_list_key = None

    return result


# ------------------------------------------------------------------
# Datas
# ------------------------------------------------------------------

def _parse_started_at(fm: dict, stem: str) -> datetime:
    if "started_at" in fm:
        try:
            return datetime.fromisoformat(fm["started_at"])
        except ValueError:
            pass
    if "date" in fm:
        try:
            return datetime.strptime(fm["date"], "%Y-%m-%d")
        except ValueError:
            pass
    # Fallback: data do nome do arquivo
    try:
        return datetime.strptime(stem[:10], "%Y-%m-%d")
    except ValueError:
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def _parse_ended_at(fm: dict, started_at: datetime) -> datetime | None:
    if "ended_at" in fm and fm["ended_at"]:
        try:
            return datetime.fromisoformat(fm["ended_at"])
        except ValueError:
            pass
    if "duration" in fm:
        secs = _parse_duration_str(fm["duration"])
        if secs > 0:
            return started_at + timedelta(seconds=secs)
    return None


def _parse_duration_str(s: str) -> int:
    """'47min 24s' → 1644. Retorna 0 em falha."""
    if not s or s.strip() in ("—", "-", ""):
        return 0
    m = re.search(r'(?:(\d+)min\s*)?(?:(\d+)s)?', s)
    if not m:
        return 0
    minutes = int(m.group(1)) if m.group(1) else 0
    seconds = int(m.group(2)) if m.group(2) else 0
    return minutes * 60 + seconds


# ------------------------------------------------------------------
# Body
# ------------------------------------------------------------------

def _parse_body(body: str) -> tuple[list[Topic], list[NextStep], list[str]]:
    topics: list[Topic] = []
    next_steps: list[NextStep] = []
    tldr: list[str] = []

    section: str | None = None  # nome da seção atual
    current_topic: Topic | None = None
    pre_heading_lines: list[str] = []
    found_first_heading = False

    for raw_line in body.splitlines():
        line = raw_line.rstrip()

        # Pula H1 e linha horizontal
        if line.startswith("# ") or line == "---":
            continue

        # Novo heading H2 ou H3 (formatos antigo e novo do summarizer)
        is_h2 = line.startswith("## ")
        is_h3 = line.startswith("### ")
        if is_h2 or is_h3:
            found_first_heading = True
            heading = line[4:].strip() if is_h3 else line[3:].strip()

            if heading.upper() == "TLDR":
                section = "tldr"
                current_topic = None
            elif heading in ("Próximos Passos", "Proximos Passos", "Next Steps"):
                section = "next_steps"
                current_topic = None
            else:
                section = "topic"
                current_topic = Topic(title=heading)
                topics.append(current_topic)
            continue

        if not found_first_heading:
            pre_heading_lines.append(line)
            continue

        if not line:
            continue

        # Conteúdo dentro da seção
        if section == "tldr":
            if line.startswith("- "):
                tldr.append(line[2:].strip())
            else:
                # Formato antigo: texto corrido
                tldr.append(line.strip())

        elif section == "next_steps":
            if line.startswith("- "):
                next_steps.append(NextStep(action=line[2:].strip()))
            else:
                # Formato antigo: texto corrido
                text = line.strip()
                if text:
                    next_steps.append(NextStep(action=text))

        elif section == "topic" and current_topic is not None:
            if re.match(r'^  - |^    - ', raw_line):
                # Sub-bullet (formato novo)
                if current_topic.bullets:
                    current_topic.bullets[-1].sub_bullets.append(line.strip().lstrip("- "))
            elif line.startswith("- "):
                current_topic.bullets.append(Bullet(text=line[2:].strip()))
            else:
                # Formato antigo: texto corrido → cada linha vira um bullet
                text = line.strip()
                if text:
                    current_topic.bullets.append(Bullet(text=text))

    # Fallback: TLDR inline antes do primeiro heading
    if not tldr:
        for line in pre_heading_lines:
            m = re.match(r'^\*\*TLDR[:\s]*\*\*\s*(.*)', line, re.IGNORECASE)
            if m and m.group(1).strip():
                tldr.append(m.group(1).strip())

    return topics, next_steps, tldr


# ------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------

def _title_from_stem(stem: str) -> str:
    """Remove prefixo de data do nome do arquivo para obter o título."""
    if len(stem) > 11 and stem[10] in (" ", "_"):
        return stem[11:].strip()
    return stem
