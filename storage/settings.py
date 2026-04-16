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
