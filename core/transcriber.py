from dataclasses import dataclass


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str
    speaker: str = ""


class Transcriber:
    """Utilitários para formatação de segmentos de transcrição.
    A transcrição em si é feita via Groq API em workers.py.
    """

    def segments_to_text(self, segments: list[TranscriptionSegment]) -> str:
        clean_segments = [seg for seg in segments if seg.text.strip()]
        if not any(seg.speaker for seg in clean_segments):
            return " ".join(seg.text.strip() for seg in clean_segments)

        lines: list[str] = []
        current_label = ""
        current_parts: list[str] = []

        def flush_current():
            nonlocal current_label, current_parts
            if not current_parts:
                return
            text = " ".join(current_parts).strip()
            lines.append(f"{current_label}: {text}" if current_label else text)
            current_label = ""
            current_parts = []

        for seg in sorted(clean_segments, key=lambda s: (s.start, s.end)):
            label = _speaker_label(seg.speaker)
            text = seg.text.strip()

            if label != current_label:
                flush_current()
                current_label = label
            current_parts.append(text)

        flush_current()
        return "\n".join(lines)


def _speaker_label(speaker: str) -> str:
    return {
        "mic": "eu",
        "microphone": "eu",
        "eu": "eu",
        "system": "outros",
        "loopback": "outros",
        "outros": "outros",
    }.get(speaker, "")
