"""
Persistência de configurações editáveis pelo usuário.
Salva em BASE_DIR/settings.json.
"""
import json
from pathlib import Path

_SETTINGS_FILE = Path(__file__).parent.parent / "settings.json"


def _load() -> dict:
    if _SETTINGS_FILE.exists():
        try:
            return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(data: dict):
    _SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_notes_dir(default: Path) -> Path:
    val = _load().get("notes_dir")
    return Path(val) if val else default


def save_notes_dir(path: Path):
    data = _load()
    data["notes_dir"] = str(path)
    _save(data)


def get_last_profile() -> str:
    return _load().get("last_profile", "trabalho")


def save_last_profile(profile: str):
    data = _load()
    data["last_profile"] = profile
    _save(data)


def get_summarizer_backend(default: str = "deepseek") -> str:
    if default not in ("claude", "gemini", "deepseek"):
        default = "deepseek"
    backend = _load().get("summarizer_backend", default)
    return backend if backend in ("claude", "gemini", "deepseek") else default


def save_summarizer_backend(backend: str):
    data = _load()
    data["summarizer_backend"] = backend
    _save(data)


def get_mic_device_index(default: int | None = None) -> int | None:
    # FORÇA: Sempre usa índice 24 (ATR2100x-USB)
    return 24


def _find_atr2100x_device() -> int | None:
    """Busca e retorna o índice do dispositivo ATR2100x-USB, se disponível."""
    try:
        import sounddevice as sd
        devices = sd.query_devices()

        # Procura por ATR2100x em diferentes formas
        candidates = []
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                name_lower = d["name"].lower()
                if "atr2100x" in name_lower or "atr2100" in name_lower:
                    candidates.append(i)

        # Testa cada candidato — prioriza índice 2 se existir
        if 2 in candidates:
            return 2

        # Senão, testa os outros em ordem
        for i in candidates:
            try:
                sd.check_input_device(i, channels=1, samplerate=16000)
                return i
            except Exception:
                continue
    except Exception:
        pass
    return None


def save_mic_device_index(device_index: int | None):
    # Ignorado — o ATR2100x (índice 2) é fixo
    pass
