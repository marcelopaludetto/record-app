"""
Transcrição via API da Groq (Whisper hospedado em LPU).
Muito mais rápido que inferência local — gratuito com rate limit generoso.

Limite por requisição: 25 MB. Arquivos maiores são divididos em chunks automaticamente.
Limite gratuito: 7.200 segundos de áudio/hora, 28.800/dia.
"""
import io
import json
import sys
import wave
import tempfile
from pathlib import Path

GROQ_MAX_BYTES = 24 * 1024 * 1024  # 24 MB (margem de segurança)


def _split_wav(audio_path: Path, max_bytes: int) -> list[tuple[Path, float]]:
    """
    Divide um WAV em chunks de até max_bytes.
    Retorna lista de (arquivo_temporário, offset_segundos).
    """
    with wave.open(str(audio_path), "rb") as wf:
        n_channels  = wf.getnchannels()
        sampwidth   = wf.getsampwidth()
        framerate   = wf.getframerate()
        n_frames    = wf.getnframes()

        bytes_per_frame = n_channels * sampwidth
        frames_per_chunk = max_bytes // bytes_per_frame
        seconds_per_chunk = frames_per_chunk / framerate

        chunks: list[tuple[Path, float]] = []
        offset_frames = 0

        while offset_frames < n_frames:
            wf.setpos(offset_frames)
            data = wf.readframes(min(frames_per_chunk, n_frames - offset_frames))

            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            with wave.open(tmp.name, "wb") as out:
                out.setnchannels(n_channels)
                out.setsampwidth(sampwidth)
                out.setframerate(framerate)
                out.writeframes(data)

            offset_seconds = offset_frames / framerate
            chunks.append((Path(tmp.name), offset_seconds))
            offset_frames += frames_per_chunk

    return chunks


def _transcribe_chunk(client, chunk_path: Path, model: str, language: str, offset: float, prompt: str = "") -> list[dict]:
    with open(chunk_path, "rb") as f:
        kwargs = dict(
            file=(chunk_path.name, f),
            model=model,
            language=language,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
        if prompt:
            kwargs["prompt"] = prompt
        result = client.audio.transcriptions.create(**kwargs)

    segments = []
    for seg in (result.segments or []):
        # Groq pode retornar dict ou objeto dependendo da versão do SDK
        text  = (seg["text"]  if isinstance(seg, dict) else seg.text).strip()
        start = (seg["start"] if isinstance(seg, dict) else seg.start)
        end   = (seg["end"]   if isinstance(seg, dict) else seg.end)
        if text:
            segments.append({
                "start": round(start + offset, 2),
                "end":   round(end   + offset, 2),
                "text":  text,
            })
            print(f"TEXT:{text}", file=sys.stderr, flush=True)

    if not segments and result.text and result.text.strip():
        segments = [{"start": round(offset, 2), "end": round(offset, 2), "text": result.text.strip()}]
        print(f"TEXT:{result.text.strip()}", file=sys.stderr, flush=True)

    return segments


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "audio_path obrigatório"}))
        sys.exit(1)

    audio_path = Path(sys.argv[1])
    model     = sys.argv[2] if len(sys.argv) > 2 else "whisper-large-v3-turbo"
    language  = sys.argv[3] if len(sys.argv) > 3 else "pt"
    api_key   = sys.argv[4] if len(sys.argv) > 4 else ""
    prompt    = sys.argv[5] if len(sys.argv) > 5 else ""

    if not audio_path.exists():
        print(json.dumps({"error": f"Arquivo não encontrado: {audio_path}"}))
        sys.exit(1)

    if not api_key:
        print(json.dumps({"error": "GROQ_API_KEY não configurada em config.py"}))
        sys.exit(1)

    print("PROGRESS:5", file=sys.stderr, flush=True)

    from groq import Groq
    client = Groq(api_key=api_key)

    file_size = audio_path.stat().st_size

    if file_size <= GROQ_MAX_BYTES:
        # Arquivo pequeno — envia direto
        chunks = [(audio_path, 0.0)]
        temp_files = []
    else:
        # Arquivo grande — divide em chunks
        n_chunks = (file_size // GROQ_MAX_BYTES) + 1
        print(f"PROGRESS:8", file=sys.stderr, flush=True)
        print(f"TEXT:[Arquivo grande: dividindo em {n_chunks} partes...]", file=sys.stderr, flush=True)
        chunks = _split_wav(audio_path, GROQ_MAX_BYTES)
        temp_files = [c[0] for c in chunks]

    all_segments: list[dict] = []
    n = len(chunks)

    for i, (chunk_path, offset) in enumerate(chunks):
        pct = 10 + int((i / n) * 85)
        print(f"PROGRESS:{pct}", file=sys.stderr, flush=True)
        segs = _transcribe_chunk(client, chunk_path, model, language, offset, prompt)
        all_segments.extend(segs)

    # Remove arquivos temporários
    for tmp in temp_files:
        try:
            tmp.unlink()
        except Exception:
            pass

    print("PROGRESS:100", file=sys.stderr, flush=True)
    print(json.dumps(all_segments, ensure_ascii=False))


if __name__ == "__main__":
    main()
