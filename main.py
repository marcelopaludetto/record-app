import sys
import os
import ctypes
from pathlib import Path

# Garante que o diretório raiz do projeto está no path
sys.path.insert(0, str(Path(__file__).parent))

# Diz ao Windows que este é um app independente (não agrupar com pythonw.exe)
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Marcelo.MeetingRecorder")
except Exception:
    pass

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from config import APP_NAME
from ui.main_window import MainWindow

_SOCKET_NAME = "MeetingRecorderSingleInstance"


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")

    # Instância única: tenta conectar em uma instância já rodando
    socket = QLocalSocket()
    socket.connectToServer(_SOCKET_NAME)
    if socket.waitForConnected(300):
        # Já existe uma instância — envia sinal para ela aparecer e sai
        socket.write(b"show")
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        sys.exit(0)

    # Nenhuma instância rodando — cria o servidor local
    server = QLocalServer()
    QLocalServer.removeServer(_SOCKET_NAME)  # limpa socket órfão de crash anterior
    server.listen(_SOCKET_NAME)

    # Carrega stylesheet
    qss_path = Path(__file__).parent / "ui" / "style.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

    # Ícone da aplicação (janela + barra de tarefas)
    icon_path = Path(__file__).parent / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()

    # Quando outra instância tentar abrir, traz a janela para frente
    def _on_new_connection():
        conn = server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(300)
            window.showNormal()
            window.activateWindow()
            window.raise_()
            conn.disconnectFromServer()

    server.newConnection.connect(_on_new_connection)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
