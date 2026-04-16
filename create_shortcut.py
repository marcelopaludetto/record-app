import sys
from pathlib import Path

# Remove entradas do VLibras do sys.path para evitar conflito com win32com
sys.path = [p for p in sys.path if "VLibras" not in p]

try:
    import win32com.client
    from win32com.propsys import propsys, pscon
except ImportError:
    sys.exit("Erro: pywin32 não encontrado. Execute: pip install pywin32")

APP_DIR = Path(__file__).parent.resolve()
PYTHONW = APP_DIR / "venv" / "Scripts" / "pythonw.exe"
MAIN_PY = APP_DIR / "main.py"
ICON = APP_DIR / "icon.ico"
APP_ID = "Marcelo.MeetingRecorder"
LNK_PATH = Path.home() / "Desktop" / "Meeting Recorder.lnk"

shell = win32com.client.Dispatch("WScript.Shell")
shortcut = shell.CreateShortCut(str(LNK_PATH))
shortcut.TargetPath = str(PYTHONW)
shortcut.Arguments = f'"{MAIN_PY}"'
shortcut.WorkingDirectory = str(APP_DIR)
shortcut.Description = "Meeting Recorder"
if ICON.exists():
    shortcut.IconLocation = str(ICON)
shortcut.save()

# Define o AppUserModelID no atalho — necessário para o pin na barra de tarefas
GPS_READWRITE = 2
store = propsys.SHGetPropertyStoreFromParsingName(
    str(LNK_PATH), None, GPS_READWRITE, propsys.IID_IPropertyStore
)
store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType(APP_ID))
store.Commit()

print(f"Atalho criado: {LNK_PATH}")
print("Agora clique com o botão direito no atalho e escolha 'Fixar na barra de tarefas'.")
