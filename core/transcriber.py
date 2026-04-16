from dataclasses import dataclass


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str


class Transcriber:
    """Utilitários para formatação de segmentos de transcrição.
    A transcrição em si é feita via Groq API em workers.py.
    """

    def segments_to_text(self, segments: list[TranscriptionSegment]) -> str:
        return " ".join(seg.text for seg in segments)

