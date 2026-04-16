from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from config import TEMPLATES_DIR, NOTES_DIR
from storage.models import Meeting
DAYS_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
MONTHS_SHORT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


class DocumentExporter:
    def __init__(
        self,
        templates_dir: Path = TEMPLATES_DIR,
        output_dir: Path = NOTES_DIR,
    ):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir), encoding="utf-8"),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def export_markdown(self, meeting: Meeting) -> Path:
        template = self._env.get_template("meeting_template.md.j2")

        started = meeting.started_at
        # "Wed, 25 Mar 26"
        day_name = DAYS_PT[started.weekday()]
        month_name = MONTHS_SHORT[started.month - 1]
        date_str = f"{day_name}, {started.day} {month_name} {str(started.year)[2:]}"

        content = template.render(
            title=meeting.title,
            date_iso=meeting.started_at.strftime("%Y-%m-%d"),
            started_at_iso=meeting.started_at.isoformat(),
            ended_at_iso=meeting.ended_at.isoformat() if meeting.ended_at else "",
            date_str=date_str,
            topics=meeting.topics,
            next_steps=meeting.next_steps,
            tldr=meeting.tldr,
            transcript=meeting.transcript_text or "",
            generated_at=datetime.now().strftime("%d/%m/%Y %H:%M"),
            duration=meeting.duration_label,
            tipo_agenda=meeting.tipo_agenda or "",
            temas=meeting.temas,
        )

        filename = _make_filename(meeting)
        output_path = self.output_dir / filename
        output_path.write_text(content, encoding="utf-8")
        return output_path


def _make_filename(meeting: Meeting) -> str:
    date_str = meeting.started_at.strftime("%Y-%m-%d")
    title = meeting.title.strip()
    _is_generic = (
        not title
        or title.lower().startswith("reunião")
        or title.lower().startswith("meeting")
        or title.lower().startswith("gravação")
        or title.lower().startswith("recording")
    )
    if _is_generic:
        return f"{date_str}.md"
    safe_title = "".join(
        c if (c.isalnum() or c in " -_áàâãéèêíìîóòôõúùûçÁÀÂÃÉÈÊÍÌÎÓÒÔÕÚÙÛÇ") else " "
        for c in title
    ).strip()
    safe_title = safe_title[:60].strip()
    return f"{date_str} {safe_title}.md"
