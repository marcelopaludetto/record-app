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
_NOTES_DIR_DEFAULT = Path(r"C:\Users\Marcelo\Documents\Notes")

# Carrega NOTES_DIR do settings.json se o usuário tiver alterado
from storage.settings import get_notes_dir as _get_notes_dir
NOTES_DIR = _get_notes_dir(_NOTES_DIR_DEFAULT)

# Garantir que os diretórios existem
for _dir in [AUDIO_DIR, TRANSCRIPTIONS_DIR, NOTES_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# Transcrição via Groq API
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"  # whisper-large-v3-turbo | whisper-large-v3 | distil-whisper-large-v3-en
WHISPER_LANGUAGE   = "pt"
# Vocabulário para melhorar o reconhecimento de nomes e termos específicos.
# Separe palavras/frases por vírgula. Ex: "Marcelo, ClickUp, sprint, roadmap"
WHISPER_PROMPT     = "Marcelo, Marcelo, Alurona, EFAF, EFAI, Alurona, EFAF, Daiane, Jéssica, Deia, Bina, Eve, Clari, Lu, Alura Start, EM, forms."

# Sumarização via Anthropic Claude / Google Gemini
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_MODEL   = "claude-haiku-4-5-20251001"
SUMMARIZER_BACKEND = "claude"  # "claude" | "gemini"

# Áudio
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1

# Dispositivos de áudio (None = padrão do sistema)
# Altere esses valores para fixar um dispositivo específico
MIC_DEVICE_INDEX: int | None = None       # None = microfone padrão
LOOPBACK_DEVICE_INDEX: int | None = None  # None = detecta automaticamente

# Correções de nomes: como a IA/Whisper escreve → como deve aparecer no Obsidian
# Chave: variação incorreta (case-insensitive)
# Valor: forma canônica que será usada no [[wikilink]]
NAME_ALIASES: dict[str, str] = {
    "Carol":    "Karol",
    "Lis":      "Liz",
    "Isa":      "Isabella",
    "Gi":      "Giovana",
    "Lu":      "Luana",
}

# App
APP_NAME = "Meeting Recorder"
APP_VERSION = "0.1.0"
