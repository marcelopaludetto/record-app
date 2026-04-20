from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Bullet:
    text: str
    sub_bullets: list[str] = field(default_factory=list)


@dataclass
class Topic:
    title: str
    bullets: list[Bullet] = field(default_factory=list)


@dataclass
class NextStep:
    action: str


@dataclass
class Meeting:
    title: str
    started_at: datetime = field(default_factory=datetime.now)
    id: int | None = None
    ended_at: datetime | None = None
    status: str = "recording"  # recording | transcribing | summarizing | done | error
    audio_path: Path | None = None
    transcript_path: Path | None = None
    output_md_path: Path | None = None
    transcript_text: str = ""
    topics: list[Topic] = field(default_factory=list)
    next_steps: list[NextStep] = field(default_factory=list)
    tldr: list[str] = field(default_factory=list)
    whisper_model: str = ""
    ollama_model: str = ""
    error_message: str = ""
    # Campos estruturados do novo prompt
    tipo_agenda: str = ""           # 1on1 | com cliente | followup | time todo
    temas: list[str] = field(default_factory=list)  # tags temáticas da reunião
    entities: list[dict] = field(default_factory=list)  # [{"name": "Alana", "type": "person"}, ...]
    profile: str = "trabalho"  # "trabalho" | "terapia"

    @property
    def duration_seconds(self) -> int:
        if self.ended_at and self.started_at:
            return int((self.ended_at - self.started_at).total_seconds())
        return 0

    @property
    def duration_label(self) -> str:
        s = self.duration_seconds
        if s == 0:
            return "—"
        m, sec = divmod(s, 60)
        return f"{m}min {sec:02d}s" if m else f"{sec}s"
