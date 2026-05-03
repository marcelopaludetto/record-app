import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Diretórios
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
AUDIO_DIR = DATA_DIR / "audio"
TRANSCRIPTIONS_DIR = DATA_DIR / "transcriptions"
TEMPLATES_DIR = BASE_DIR / "templates"
DB_PATH = DATA_DIR / "meetings.db"
PERSONAL_TERMS_PATH = BASE_DIR / "personal_terms.json"
_NOTES_DIR_DEFAULT = Path(os.getenv("NOTES_DIR", "")) or Path.home() / "Documents" / "Notes"

# Carrega settings.json se o usuário tiver alterado configurações pela UI
from storage.settings import get_notes_dir as _get_notes_dir, get_summarizer_backend as _get_summarizer_backend
NOTES_DIR = _get_notes_dir(_NOTES_DIR_DEFAULT)

# Garantir que os diretórios existem
for _dir in [AUDIO_DIR, TRANSCRIPTIONS_DIR, NOTES_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# Transcrição via Groq API
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"  # whisper-large-v3-turbo | whisper-large-v3 | distil-whisper-large-v3-en
WHISPER_LANGUAGE   = "pt"
_PERSONAL_TERMS = {}
if PERSONAL_TERMS_PATH.exists():
    try:
        _PERSONAL_TERMS = json.loads(PERSONAL_TERMS_PATH.read_text(encoding="utf-8"))
    except Exception:
        _PERSONAL_TERMS = {}

# Contexto enviado ao Whisper/Groq para orientar idioma, grafias e termos recorrentes.
# Isto é uma dica de transcrição, não uma regra rígida. Configure termos pessoais em
# personal_terms.json, que fica fora do Git.
WHISPER_PROMPT = str(_PERSONAL_TERMS.get("whisper_prompt", ""))

# Sumarização via Anthropic Claude / Google Gemini / DeepSeek
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY  = os.getenv("DEEPSEEK_API_KEY", "")
ANTHROPIC_MODEL   = "claude-haiku-4-5-20251001"
DEEPSEEK_MODEL    = "deepseek-v4-flash"
_SUMMARIZER_BACKEND_DEFAULT = os.getenv("SUMMARIZER_BACKEND", "deepseek")
SUMMARIZER_BACKEND = _get_summarizer_backend(_SUMMARIZER_BACKEND_DEFAULT)  # "claude" | "gemini" | "deepseek"

# Áudio
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1

# Dispositivos de áudio (None = padrão do sistema)
# Altere esses valores para fixar um dispositivo específico
MIC_DEVICE_INDEX: int | None = None       # None = microfone padrão
LOOPBACK_DEVICE_INDEX: int | None = None  # None = detecta automaticamente

# Correções de nomes: como a IA/Whisper escreve → como deve aparecer no Obsidian.
# Chave: variação incorreta (case-insensitive).
# Valor: forma canônica.
#   - Padrão: vira [[wikilink]] no Obsidian.
#   - Sufixo "*" no canônico: só corrige a grafia, SEM wikilink (use para ferramentas
#     SaaS de terceiros que são apenas correção ortográfica, ex: "Gemini*", "GPT*").
# Aplicado SEMPRE — independente das entidades retornadas pelo LLM.
NAME_ALIASES: dict[str, str] = {
    str(alias): str(canonical)
    for alias, canonical in (_PERSONAL_TERMS.get("name_aliases") or {}).items()
}

# App
APP_NAME = "Meeting Recorder"
APP_VERSION = "0.1.0"
