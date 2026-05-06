"""
Gravação de áudio: microfone + loopback do sistema (áudio do Teams/outros).

Estratégia:
- Mic: sounddevice.InputStream (16kHz mono)
- Loopback: pyaudiowpatch (48kHz stereo → convertido para 16kHz mono)
- Ambos gravados em paralelo, misturados no save()
"""
import wave
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd

from config import AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, DATA_DIR


def _log(msg: str):
    """Log em console E em arquivo."""
    print(msg)
    log_file = DATA_DIR / "recorder.log"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


class AudioRecorder:
    def __init__(
        self,
        mic_device: int | None = None,
        loopback_device: int | None = None,
        sample_rate: int = AUDIO_SAMPLE_RATE,
    ):
        self.mic_device = mic_device
        self.loopback_device = loopback_device  # índice do dispositivo loopback WASAPI
        self.sample_rate = sample_rate

        self._mic_frames: list[np.ndarray] = []
        self._loopback_frames: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._mic_stream = None
        self._loopback_thread: threading.Thread | None = None
        self._loopback_rate: int = 48000  # será atualizado ao abrir o stream
        self._mic_rate: int = AUDIO_SAMPLE_RATE  # taxa real do mic (pode ser 48000)
        self.is_recording = False

    # ------------------------------------------------------------------
    # Utilitários estáticos
    # ------------------------------------------------------------------

    @staticmethod
    def list_mic_devices() -> list[dict]:
        result = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0 and "loopback" not in d["name"].lower() and sd.query_hostapis()[d["hostapi"]]["name"] == "Windows WASAPI":
                result.append({"index": i, "name": d["name"]})
        return result

    @staticmethod
    def list_loopback_devices() -> list[dict]:
        """Retorna dispositivos WASAPI loopback (capturam o áudio do sistema)."""
        try:
            import pyaudiowpatch as pyaudio
            p = pyaudio.PyAudio()
            devices = [
                {
                    "index": d["index"],
                    "name": d["name"],
                    "channels": d["maxInputChannels"],
                    "rate": int(d["defaultSampleRate"]),
                }
                for d in p.get_loopback_device_info_generator()
            ]
            p.terminate()
            return devices
        except Exception:
            return []

    @staticmethod
    def get_default_loopback() -> dict | None:
        """Retorna o dispositivo loopback do output padrão."""
        try:
            import pyaudiowpatch as pyaudio
            p = pyaudio.PyAudio()
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_out = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            result = None
            for loopback in p.get_loopback_device_info_generator():
                if default_out["name"] in loopback["name"]:
                    result = {
                        "index": loopback["index"],
                        "name": loopback["name"],
                        "channels": loopback["maxInputChannels"],
                        "rate": int(loopback["defaultSampleRate"]),
                    }
                    break
            # fallback: primeiro loopback disponível
            if result is None:
                for loopback in p.get_loopback_device_info_generator():
                    result = {
                        "index": loopback["index"],
                        "name": loopback["name"],
                        "channels": loopback["maxInputChannels"],
                        "rate": int(loopback["defaultSampleRate"]),
                    }
                    break
            p.terminate()
            return result
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Gravação
    # ------------------------------------------------------------------

    def start(self):
        if self.is_recording:
            return
        self._mic_frames = []
        self._loopback_frames = []
        self._stop_event.clear()
        self.is_recording = True

        # Stream do microfone via sounddevice
        def _mic_callback(indata, frames, time_info, status):
            if not self._stop_event.is_set():
                with self._lock:
                    self._mic_frames.append(indata.copy())

        mic_device = self.mic_device
        stream_rate = self.sample_rate
        self._mic_rate = stream_rate
        try:
            # Tenta com 1 canal a 16kHz primeiro
            self._mic_stream = sd.InputStream(
                samplerate=stream_rate,
                channels=1,
                dtype="int16",
                device=mic_device,
                callback=_mic_callback,
                blocksize=1024,
            )
            self._mic_stream.start()
            self._mic_rate = stream_rate
            actual_device = self._mic_stream.device
            device_info = sd.query_devices(actual_device)
            _log(f"[RECORDER] Gravando com: Índice {actual_device} | {device_info['name']} @ {stream_rate}Hz")
        except Exception as e:
            # Se falhar, tenta com 48kHz (comum em USB)
            if mic_device is not None:
                try:
                    _log(f"[RECORDER] Falha com {stream_rate}Hz, tentando com 48000Hz...")
                    stream_rate = 48000
                    self._mic_rate = 48000

                    def _mic_callback_48k(indata, frames, time_info, status):
                        if not self._stop_event.is_set():
                            with self._lock:
                                self._mic_frames.append(indata.copy())

                    self._mic_stream = sd.InputStream(
                        samplerate=stream_rate,
                        channels=1,
                        dtype="int16",
                        device=mic_device,
                        callback=_mic_callback_48k,
                        blocksize=1024,
                    )
                    self._mic_stream.start()
                    self._mic_rate = 48000
                    actual_device = self._mic_stream.device
                    device_info = sd.query_devices(actual_device)
                    _log(f"[RECORDER] Gravando com: Índice {actual_device} | {device_info['name']} @ 48000Hz")
                except Exception as e2:
                    _log(f"[RECORDER] Falha ao abrir dispositivo {mic_device}, voltando para padrão")
                    self._mic_stream = sd.InputStream(
                        samplerate=self.sample_rate,
                        channels=1,
                        dtype="int16",
                        device=None,
                        callback=_mic_callback,
                        blocksize=1024,
                    )
                    self._mic_stream.start()
                    self._mic_rate = self.sample_rate
                    actual_device = self._mic_stream.device
                    device_info = sd.query_devices(actual_device)
                    _log(f"[RECORDER] Gravando com padrão: Índice {actual_device} | {device_info['name']}")
            else:
                raise

        # Stream de loopback via pyaudiowpatch (thread separada)
        if self.loopback_device is not None:
            self._loopback_thread = threading.Thread(
                target=self._run_loopback,
                daemon=True,
            )
            self._loopback_thread.start()

    def _run_loopback(self):
        """Captura áudio do sistema via WASAPI loopback em thread própria."""
        try:
            import pyaudiowpatch as pyaudio
            devices = self.list_loopback_devices()
            dev_info = next((d for d in devices if d["index"] == self.loopback_device), None)
            if dev_info is None:
                return

            self._loopback_rate = dev_info["rate"]
            channels = dev_info["channels"]
            chunk = 1024

            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=self._loopback_rate,
                input=True,
                input_device_index=self.loopback_device,
                frames_per_buffer=chunk,
            )

            while not self._stop_event.is_set():
                data = stream.read(chunk, exception_on_overflow=False)
                arr = np.frombuffer(data, dtype=np.int16).reshape(-1, channels)
                # Converte para mono
                mono = arr.mean(axis=1).astype(np.int16)
                with self._lock:
                    self._loopback_frames.append(mono)

            stream.stop_stream()
            stream.close()
            p.terminate()
        except Exception as e:
            pass  # loopback opcional — não quebra a gravação do mic

    def stop(self, output_path: Path) -> Path:
        if not self.is_recording:
            raise RuntimeError("Gravação não está em andamento.")

        self._stop_event.set()
        self.is_recording = False

        if self._mic_stream:
            self._mic_stream.stop()
            self._mic_stream.close()
            self._mic_stream = None

        if self._loopback_thread:
            self._loopback_thread.join(timeout=3)
            self._loopback_thread = None

        if not self._mic_frames:
            raise RuntimeError("Nenhum áudio capturado pelo microfone.")

        with self._lock:
            mic_audio = np.concatenate(self._mic_frames, axis=0).flatten()
            loopback_raw = (
                np.concatenate(self._loopback_frames, axis=0).flatten()
                if self._loopback_frames
                else None
            )

        # Resample mic se foi gravado a taxa diferente
        if self._mic_rate != self.sample_rate:
            ratio = self.sample_rate / self._mic_rate
            new_len = int(len(mic_audio) * ratio)
            indices = np.linspace(0, len(mic_audio) - 1, new_len)
            mic_audio = np.interp(indices, np.arange(len(mic_audio)), mic_audio).astype(np.int16)

        # Mistura mic + loopback (se disponível)
        mixed = _mix_audio(mic_audio, loopback_raw, self._loopback_rate, self.sample_rate)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(mixed.tobytes())

        return output_path

    def get_mixed_audio(self) -> np.ndarray:
        """Snapshot mono int16 do áudio capturado até agora (mic + loopback mixados).
        Thread-safe — para uso do transcritor ao vivo sem interferir na gravação.
        """
        with self._lock:
            if not self._mic_frames:
                return np.array([], dtype=np.int16)
            mic = np.concatenate(self._mic_frames, axis=0).flatten()
            loop = (
                np.concatenate(self._loopback_frames, axis=0).flatten()
                if self._loopback_frames else None
            )
        return _mix_audio(mic, loop, self._loopback_rate, self.sample_rate)

    @property
    def recorded_seconds(self) -> float:
        with self._lock:
            if not self._mic_frames:
                return 0.0
            return sum(f.shape[0] for f in self._mic_frames) / self.sample_rate

    @property
    def has_loopback(self) -> bool:
        return self.loopback_device is not None


# ------------------------------------------------------------------
# Mixagem de áudio
# ------------------------------------------------------------------

def _mix_audio(mic: np.ndarray, loopback: np.ndarray | None,
               loopback_rate: int, target_rate: int) -> np.ndarray:
    """Reamostrar loopback para target_rate e misturar com mic."""
    if loopback is None or len(loopback) == 0:
        return mic.astype(np.int16)

    # Reamostrar loopback: 48kHz → 16kHz
    if loopback_rate != target_rate:
        ratio = target_rate / loopback_rate
        new_len = int(len(loopback) * ratio)
        indices = np.linspace(0, len(loopback) - 1, new_len)
        loopback_resampled = np.interp(indices, np.arange(len(loopback)), loopback).astype(np.int16)
    else:
        loopback_resampled = loopback.astype(np.int16)

    # Iguala tamanhos
    min_len = min(len(mic), len(loopback_resampled))
    mic_trim = mic[:min_len].astype(np.int32)
    loop_trim = loopback_resampled[:min_len].astype(np.int32)

    # Mistura com clipping (evita overflow)
    mixed = np.clip(mic_trim + loop_trim, -32768, 32767).astype(np.int16)
    return mixed
