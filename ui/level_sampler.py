"""
Leitura de nível de áudio em background para medidores ao vivo.
"""
import math
import threading
import time as _time


def rms_to_level(rms: float) -> int:
    """Converte RMS int16 para 0-100 em escala logarítmica (-60dB→0, 0dB→100)."""
    if rms <= 0:
        return 0
    db = 20 * math.log10(max(rms, 1) / 32768.0)
    return max(0, min(100, int((db + 60) / 60 * 100)))


class LevelSampler:
    """Lê áudio de um dispositivo em background e expõe level 0-100."""

    def __init__(self):
        self.level: int = 0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start_mic(self, device_index: int | None):
        self._restart(lambda: self._mic_worker(device_index))

    def start_loopback(self, device_index: int, rate: int, channels: int):
        self._restart(lambda: self._loopback_worker(device_index, rate, channels))

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None
        self.level = 0

    def _restart(self, target):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        self._stop.clear()
        self.level = 0
        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()

    def _mic_worker(self, device_index: int | None):
        import numpy as np
        import sounddevice as sd

        def callback(indata, frames, time_info, status):
            rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
            self.level = rms_to_level(rms)

        for rate in (16000, 48000, 44100):
            if self._stop.is_set():
                break
            try:
                with sd.InputStream(
                    samplerate=rate, channels=1, dtype="int16",
                    device=device_index, callback=callback, blocksize=1024,
                ):
                    while not self._stop.is_set():
                        _time.sleep(0.05)
                break
            except Exception:
                continue
        self.level = 0

    def _loopback_worker(self, device_index: int, rate: int, channels: int):
        import numpy as np
        try:
            import pyaudiowpatch as pyaudio
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024,
            )
            while not self._stop.is_set():
                data = stream.read(1024, exception_on_overflow=False)
                arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                rms = float(np.sqrt(np.mean(arr ** 2)))
                self.level = rms_to_level(rms)
            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception:
            pass
        finally:
            self.level = 0
