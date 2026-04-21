"""
Transcrição ao vivo durante a gravação.

Lê chunks do buffer do AudioRecorder a cada N segundos e envia para a API
Groq Whisper. Não interfere com a gravação principal — apenas observa os
buffers via snapshot thread-safe.

A transcrição "oficial" continua sendo a do áudio completo pós-gravação
(melhor qualidade); a live é apenas feedback em tempo real para o usuário.
"""
import wave
import tempfile
import threading
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from config import GROQ_API_KEY, GROQ_WHISPER_MODEL, WHISPER_LANGUAGE, WHISPER_PROMPT
from core.recorder import AudioRecorder


class LiveTranscriber(QThread):
    """Emite `segment(str)` para cada trecho transcrito enquanto a gravação roda."""

    segment = pyqtSignal(str)

    def __init__(self, recorder: AudioRecorder, interval_seconds: int = 20, min_chunk_seconds: int = 5):
        super().__init__()
        self._recorder = recorder
        self._interval = interval_seconds
        self._min_samples = min_chunk_seconds * recorder.sample_rate
        self._stop_event = threading.Event()
        self._cursor = 0  # índice (em samples) do próximo chunk a enviar

    def stop(self):
        self._stop_event.set()

    def run(self):
        if not GROQ_API_KEY:
            self.segment.emit("[transcrição ao vivo indisponível: GROQ_API_KEY ausente]")
            return

        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        sr = self._recorder.sample_rate

        while not self._stop_event.wait(self._interval):
            audio = self._recorder.get_mixed_audio()
            chunk = audio[self._cursor:]
            if len(chunk) < self._min_samples:
                continue

            text = self._transcribe(client, chunk, sr)
            if text:
                self.segment.emit(text)
            self._cursor += len(chunk)

    def _transcribe(self, client, chunk, sample_rate: int) -> str:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        path = Path(tmp.name)
        try:
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(chunk.tobytes())

            with open(path, "rb") as f:
                kwargs = dict(
                    file=(path.name, f),
                    model=GROQ_WHISPER_MODEL,
                    language=WHISPER_LANGUAGE,
                    response_format="text",
                )
                if WHISPER_PROMPT:
                    kwargs["prompt"] = WHISPER_PROMPT
                result = client.audio.transcriptions.create(**kwargs)

            text = result if isinstance(result, str) else getattr(result, "text", "")
            return text.strip()
        except Exception as e:
            return f"[erro na transcrição ao vivo: {e}]"
        finally:
            try:
                path.unlink()
            except Exception:
                pass
