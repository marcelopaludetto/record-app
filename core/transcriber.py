import json
import math
from dataclasses import dataclass
from pathlib import Path


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

    def label_segments_from_source_activity(
        self,
        segments: list[TranscriptionSegment],
        activity_path: Path,
    ) -> list[TranscriptionSegment]:
        if not activity_path.exists():
            return segments

        try:
            data = json.loads(activity_path.read_text(encoding="utf-8"))
            bin_seconds = float(data["bin_seconds"])
            mic_levels = [float(v) for v in data["mic"]]
            system_levels = [float(v) for v in data["system"]]
        except Exception:
            return segments

        if not mic_levels or not system_levels or bin_seconds <= 0:
            return segments

        n_bins = min(len(mic_levels), len(system_levels))
        for seg in segments:
            seg.speaker = _source_for_segment(
                seg,
                mic_levels[:n_bins],
                system_levels[:n_bins],
                bin_seconds,
            )
        return segments


def _speaker_label(speaker: str) -> str:
    return {
        "mic": "eu",
        "microphone": "eu",
        "eu": "eu",
        "system": "outros",
        "loopback": "outros",
        "outros": "outros",
    }.get(speaker, "")


def _source_for_segment(
    segment: TranscriptionSegment,
    mic_levels: list[float],
    system_levels: list[float],
    bin_seconds: float,
) -> str:
    start_bin = max(0, int(segment.start / bin_seconds))
    end_bin = min(len(mic_levels), max(start_bin + 1, int(math.ceil(segment.end / bin_seconds))))

    mic_energy = _mean_square(mic_levels[start_bin:end_bin])
    system_energy = _mean_square(system_levels[start_bin:end_bin])

    if mic_energy <= 0 and system_energy <= 0:
        return ""
    if mic_energy >= system_energy * 1.15:
        return "mic"
    if system_energy >= mic_energy * 1.15:
        return "system"
    return "mic" if mic_energy >= system_energy else "system"


def _mean_square(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(v * v for v in values) / len(values)
