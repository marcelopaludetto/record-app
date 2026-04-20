import subprocess
import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTabWidget,
    QStatusBar, QMessageBox, QGroupBox, QPlainTextEdit,
    QSystemTrayIcon, QMenu, QFileDialog, QInputDialog, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QAction, QCloseEvent

import config
from config import APP_NAME, APP_VERSION
from storage.settings import save_notes_dir
from core.meeting_controller import MeetingController
from ui.workers import ProcessingWorker, TxtProcessingWorker
from ui.meeting_dialog import NewMeetingDialog
from ui.tray_icon import make_tray_icon
from ui.agent_widget import AgentWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._controller = MeetingController()
        self._worker: ProcessingWorker | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._update_timer)
        self._elapsed_seconds = 0
        self._notes_dir = config.NOTES_DIR
        self._setup_ui()
        self._setup_tray()
        QTimer.singleShot(0, self._check_api)

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(800, 560)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(self._build_recorder_tab(), "⏺  Gravar")
        tabs.addTab(self._build_agent_tab(), "🤖  Assistente")
        root.addWidget(tabs)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Pronto.")

    def _build_recorder_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(16)

        # Status
        self._label_status = QLabel("Pronto para gravar")
        self._label_status.setObjectName("status_label")
        self._label_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label_status)

        # Timer
        self._label_timer = QLabel("00:00")
        self._label_timer.setObjectName("timer_label")
        self._label_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Consolas", 32, QFont.Weight.Bold)
        self._label_timer.setFont(font)
        self._label_timer.hide()
        layout.addWidget(self._label_timer)

        # Botões principais
        btn_group = QGroupBox("Controle")
        btn_layout = QHBoxLayout(btn_group)
        btn_layout.setSpacing(12)

        self._btn_start = QPushButton("▶  Iniciar Reunião")
        self._btn_start.setObjectName("btn_start")
        self._btn_start.setFixedHeight(48)
        self._btn_start.clicked.connect(self._on_start)

        self._btn_stop = QPushButton("⏹  Parar e Processar")
        self._btn_stop.setObjectName("btn_stop")
        self._btn_stop.setFixedHeight(48)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)

        self._btn_import = QPushButton("📂  Importar Áudio")
        self._btn_import.setObjectName("btn_import")
        self._btn_import.setFixedHeight(48)
        self._btn_import.clicked.connect(self._on_import_audio)

        self._btn_import_txt = QPushButton("📄  Importar TXT")
        self._btn_import_txt.setObjectName("btn_import")
        self._btn_import_txt.setFixedHeight(48)
        self._btn_import_txt.clicked.connect(self._on_import_txt)

        self._btn_folder = QPushButton("📁  Abrir Pasta Notes")
        self._btn_folder.setFixedHeight(48)
        self._btn_folder.clicked.connect(self._open_notes_folder)

        btn_layout.addWidget(self._btn_start)
        btn_layout.addWidget(self._btn_stop)
        btn_layout.addWidget(self._btn_import)
        btn_layout.addWidget(self._btn_import_txt)
        btn_layout.addWidget(self._btn_folder)
        layout.addWidget(btn_group)

        # Progresso
        progress_group = QGroupBox("Processamento")
        progress_layout = QVBoxLayout(progress_group)

        self._label_progress = QLabel("Aguardando...")
        self._label_progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self._label_progress)

        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
        progress_layout.addWidget(self._progress_bar)

        layout.addWidget(progress_group)

        # Transcrição progressiva
        transcript_group = QGroupBox("Transcrição")
        transcript_layout = QVBoxLayout(transcript_group)
        self._transcript_view = QPlainTextEdit()
        self._transcript_view.setReadOnly(True)
        self._transcript_view.setPlaceholderText("Os segmentos transcritos aparecerão aqui durante o processamento...")
        self._transcript_view.setMaximumHeight(180)
        font_t = QFont("Consolas", 9)
        self._transcript_view.setFont(font_t)
        transcript_layout.addWidget(self._transcript_view)
        layout.addWidget(transcript_group)

        layout.addStretch()

        # Pasta de saída (Notes)
        notes_row = QHBoxLayout()
        notes_row.setSpacing(6)
        self._label_notes_dir = QLabel()
        self._label_notes_dir.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._label_notes_dir.setStyleSheet("color: #585b70; font-size: 11px;")
        self._update_notes_dir_label()
        btn_change_dir = QPushButton("Alterar pasta")
        btn_change_dir.setFixedHeight(26)
        btn_change_dir.clicked.connect(self._on_change_notes_dir)
        notes_row.addWidget(QLabel("📁 Notas:"))
        notes_row.addWidget(self._label_notes_dir, stretch=1)
        notes_row.addWidget(btn_change_dir)
        layout.addLayout(notes_row)

        # Seletor de backend de sumarização
        backend_row = QHBoxLayout()
        backend_row.setSpacing(6)
        backend_row.addWidget(QLabel("🤖 Sumarização:"))
        self._combo_backend = QComboBox()
        self._combo_backend.addItems(["gemini", "claude"])
        self._combo_backend.setCurrentText(config.SUMMARIZER_BACKEND)
        self._combo_backend.setFixedWidth(100)
        self._combo_backend.currentTextChanged.connect(self._on_backend_changed)
        backend_row.addWidget(self._combo_backend)
        backend_row.addStretch()

        # API status
        self._label_api = QLabel()
        self._label_api.setAlignment(Qt.AlignmentFlag.AlignRight)
        backend_row.addWidget(self._label_api)
        layout.addLayout(backend_row)

        return tab

    def _build_agent_tab(self) -> QWidget:
        self._agent_widget = AgentWidget(self._controller)
        return self._agent_widget

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_start(self):
        dlg = NewMeetingDialog(self._controller, parent=self)
        if dlg.exec() != NewMeetingDialog.DialogCode.Accepted:
            return

        title = dlg.get_title()
        profile = dlg.get_profile()

        if not title:
            return

        try:
            self._controller.start_meeting(title, profile)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        # Mostra se está gravando loopback ou só mic
        rec = self._controller._recorder
        if rec.has_loopback:
            audio_info = "🎤 + 🔊 mic e sistema"
        else:
            audio_info = "🎤 só microfone"

        self._elapsed_seconds = 0
        self._label_timer.setText("00:00")
        self._label_timer.show()
        self._timer.start()

        self._tray.setIcon(make_tray_icon(recording=True))
        self._tray.setToolTip(f"{APP_NAME} — Gravando")
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._label_status.setText(f"⏺  Gravando: {title}  ({audio_info})")
        self._progress_bar.hide()
        self._label_progress.setText("Gravando áudio...")
        self._status_bar.showMessage(f"Gravação em andamento: {title}")

    @pyqtSlot()
    def _on_stop(self):
        self._timer.stop()
        self._btn_stop.setEnabled(False)
        self._label_status.setText("Processando...")

        try:
            self._controller.stop_recording()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao parar gravação", str(e))
            self._reset_ui()
            return

        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._label_progress.setText("Iniciando processamento...")
        self._status_bar.showMessage("Transcrevendo e gerando resumo...")

        self._transcript_view.clear()
        self._worker = ProcessingWorker(self._controller)
        self._worker.progress.connect(self._on_progress)
        self._worker.segment_text.connect(self._on_segment_text)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @pyqtSlot(str, int)
    def _on_progress(self, message: str, value: int):
        self._label_progress.setText(message)
        self._progress_bar.setValue(value)
        self._status_bar.showMessage(message)

    @pyqtSlot(str)
    def _on_finished(self, path: str):
        self._label_timer.hide()
        self._progress_bar.setValue(100)
        filename = Path(path).name
        self._label_status.setText(f"✅  Salvo: {filename}")
        self._label_progress.setText(f"Documento gerado com sucesso!")
        self._status_bar.showMessage(f"Concluído: {path}")
        self._tray.setIcon(make_tray_icon(recording=False))
        self._tray.setToolTip(APP_NAME)
        self._btn_start.setEnabled(True)

    @pyqtSlot(str)
    def _on_segment_text(self, text: str):
        self._transcript_view.appendPlainText(text)
        self._transcript_view.verticalScrollBar().setValue(
            self._transcript_view.verticalScrollBar().maximum()
        )

    @pyqtSlot(str)
    def _on_error(self, message: str):
        self._label_status.setText("❌  Erro no processamento")
        self._label_progress.setText(f"Erro: {message}")
        self._progress_bar.hide()
        self._status_bar.showMessage(f"Erro: {message}")
        self._btn_start.setEnabled(True)
        QMessageBox.critical(self, "Erro no processamento", message)

    @pyqtSlot()
    def _update_timer(self):
        self._elapsed_seconds += 1
        m, s = divmod(self._elapsed_seconds, 60)
        self._label_timer.setText(f"{m:02d}:{s:02d}")

    @pyqtSlot()
    def _on_import_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo de áudio",
            str(Path.home()),
            "Áudio (*.wav *.mp3 *.m4a *.ogg *.flac *.mp4 *.webm)",
        )
        if not path:
            return

        audio_path = Path(path)

        # Sugere o título baseado no nome do arquivo
        default_title = audio_path.stem.replace("-", " ").replace("_", " ")
        title, ok = QInputDialog.getText(
            self, "Título da reunião", "Nome da reunião:", text=default_title
        )
        if not ok or not title.strip():
            return

        profile_label, ok2 = QInputDialog.getItem(
            self, "Tipo de registro", "Tipo:", ["Trabalho", "Terapia"], 0, False
        )
        if not ok2:
            return
        profile = "terapia" if profile_label == "Terapia" else "trabalho"

        try:
            self._controller.import_audio(audio_path, title.strip(), profile)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_import.setEnabled(False)
        self._label_status.setText(f"⏳  Processando: {title}")
        self._label_progress.setText("Iniciando transcrição...")
        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._transcript_view.clear()
        self._status_bar.showMessage(f"Importando áudio: {audio_path.name}")

        self._worker = ProcessingWorker(self._controller)
        self._worker.progress.connect(self._on_progress)
        self._worker.segment_text.connect(self._on_segment_text)
        self._worker.finished.connect(self._on_import_finished)
        self._worker.error.connect(self._on_import_error)
        self._worker.start()

    @pyqtSlot()
    def _on_import_txt(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar transcrição",
            str(Path.home()),
            "Transcrição (*.txt *.vtt)",
        )
        if not path:
            return

        txt_path = Path(path)
        default_title = txt_path.stem.replace("-", " ").replace("_", " ")
        title, ok = QInputDialog.getText(
            self, "Título da reunião", "Nome da reunião:", text=default_title
        )
        if not ok or not title.strip():
            return

        profile_label, ok2 = QInputDialog.getItem(
            self, "Tipo de registro", "Tipo:", ["Trabalho", "Terapia"], 0, False
        )
        if not ok2:
            return
        profile = "terapia" if profile_label == "Terapia" else "trabalho"

        try:
            self._controller.import_txt(txt_path, title.strip(), profile)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        self._btn_start.setEnabled(False)
        self._btn_import.setEnabled(False)
        self._btn_import_txt.setEnabled(False)
        self._label_status.setText(f"⏳  Resumindo: {title}")
        self._label_progress.setText("Gerando resumo...")
        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._status_bar.showMessage(f"Processando: {txt_path.name}")

        self._worker = TxtProcessingWorker(self._controller)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_txt_finished)
        self._worker.error.connect(self._on_txt_error)
        self._worker.start()

    @pyqtSlot(str)
    def _on_txt_finished(self, path: str):
        self._btn_import_txt.setEnabled(True)
        self._on_import_finished(path)

    @pyqtSlot(str)
    def _on_txt_error(self, message: str):
        self._btn_import_txt.setEnabled(True)
        self._on_import_error(message)

    @pyqtSlot(str)
    def _on_import_finished(self, path: str):
        self._btn_import.setEnabled(True)
        self._on_finished(path)

    @pyqtSlot(str)
    def _on_import_error(self, message: str):
        self._btn_import.setEnabled(True)
        self._on_error(message)

    @pyqtSlot()
    def _open_notes_folder(self):
        subprocess.Popen(["explorer", str(self._notes_dir)], shell=True)

    # ------------------------------------------------------------------
    # System Tray
    # ------------------------------------------------------------------

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(make_tray_icon(recording=False), parent=self)
        self._tray.setToolTip(APP_NAME)

        menu = QMenu()
        action_show = QAction("Mostrar", self)
        action_show.triggered.connect(self._show_window)

        self._action_autostart = QAction("Iniciar com o Windows", self)
        self._action_autostart.setCheckable(True)
        self._action_autostart.setChecked(self._autostart_enabled())
        self._action_autostart.triggered.connect(self._toggle_autostart)

        action_quit = QAction("Sair", self)
        action_quit.triggered.connect(self._quit_app)

        menu.addAction(action_show)
        menu.addSeparator()
        menu.addAction(self._action_autostart)
        menu.addSeparator()
        menu.addAction(action_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _quit_app(self):
        self._tray.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    # ------------------------------------------------------------------
    # Autostart no Windows
    # ------------------------------------------------------------------

    _REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    _REG_NAME = "MeetingRecorder"

    def _autostart_enabled(self) -> bool:
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._REG_KEY, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, self._REG_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False

    def _toggle_autostart(self, checked: bool):
        import winreg
        from pathlib import Path
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._REG_KEY, 0, winreg.KEY_SET_VALUE)
        if checked:
            vbs = Path(__file__).parent.parent / "run.vbs"
            value = f'wscript.exe "{vbs}"'
            winreg.SetValueEx(key, self._REG_NAME, 0, winreg.REG_SZ, value)
            self._tray.showMessage(APP_NAME, "App vai iniciar automaticamente com o Windows.", 2000)
        else:
            try:
                winreg.DeleteValue(key, self._REG_NAME)
            except FileNotFoundError:
                pass
            self._tray.showMessage(APP_NAME, "Inicialização automática desativada.", 2000)
        winreg.CloseKey(key)

    def closeEvent(self, event: QCloseEvent):
        self._quit_app()

    # ------------------------------------------------------------------
    # Meet Watcher
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _reset_ui(self):
        self._timer.stop()
        self._label_timer.hide()
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_import.setEnabled(True)
        self._btn_import_txt.setEnabled(True)
        self._progress_bar.hide()
        self._label_status.setText("Pronto para gravar")
        self._label_progress.setText("Aguardando...")

    def _on_backend_changed(self, backend: str):
        from core.summarizer import Summarizer
        from core.summarizer_gemini import GeminiSummarizer
        config.SUMMARIZER_BACKEND = backend
        self._controller._summarizer = GeminiSummarizer() if backend == "gemini" else Summarizer()
        self._check_api()

    def _check_api(self):
        summarizer = self._controller._summarizer
        backend = summarizer.backend
        available = summarizer.is_available()

        if backend == "gemini" and available:
            self._label_api.setText("🟢 Gemini 2.5 Flash")
            self._label_api.setStyleSheet("color: #a6e3a1;")
        elif backend == "claude" and available:
            from config import ANTHROPIC_MODEL
            self._label_api.setText(f"🟢 Claude ({ANTHROPIC_MODEL})")
            self._label_api.setStyleSheet("color: #a6e3a1;")
        else:
            self._label_api.setText("🔴 Chave API inválida ou ausente")
            self._label_api.setStyleSheet("color: #f38ba8;")

    def _update_notes_dir_label(self):
        self._label_notes_dir.setText(str(self._notes_dir))

    @pyqtSlot()
    def _on_change_notes_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Selecionar pasta de notas", str(self._notes_dir)
        )
        if not path:
            return
        self._notes_dir = Path(path)
        self._notes_dir.mkdir(parents=True, exist_ok=True)
        save_notes_dir(self._notes_dir)
        self._update_notes_dir_label()
        self._status_bar.showMessage(f"Pasta de notas alterada: {path}")
