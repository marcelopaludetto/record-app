import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QProgressBar, QTabWidget,
    QStatusBar, QMessageBox, QPlainTextEdit,
    QSystemTrayIcon, QMenu, QFileDialog, QComboBox, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QIcon, QAction, QCloseEvent

import config
from config import APP_NAME, APP_VERSION
from storage.settings import save_notes_dir, get_last_profile, save_last_profile, save_summarizer_backend, save_mic_device_index
from core.meeting_controller import MeetingController
from ui.workers import ProcessingWorker, TxtProcessingWorker
from ui.meeting_dialog import NewMeetingDialog
from ui.import_dialog import ImportDialog
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
        self.setMinimumSize(760, 520)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_recorder_tab(), "⏺  Gravar")
        self._tabs.addTab(self._build_agent_tab(),    "🤖  Assistente")
        root.addWidget(self._tabs)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Pronto.")

    def _build_recorder_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(0)

        # ── Cabeçalho: status + API pill ─────────────────────────────
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        self._label_status = QLabel("Pronto para gravar")
        self._label_status.setObjectName("status_label")
        header.addWidget(self._label_status, stretch=1)

        self._combo_backend = QComboBox()
        self._combo_backend.addItems(["claude", "gemini", "deepseek"])
        self._combo_backend.setCurrentText(config.SUMMARIZER_BACKEND)
        self._combo_backend.setFixedWidth(98)
        self._combo_backend.setFixedHeight(24)
        self._combo_backend.currentTextChanged.connect(self._on_backend_changed)
        header.addWidget(self._combo_backend)

        self._label_api = QLabel()
        self._label_api.setObjectName("api_pill")
        self._label_api.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self._label_api)

        layout.addLayout(header)
        layout.addSpacing(16)

        # ── Timer ─────────────────────────────────────────────────────
        self._label_timer = QLabel("00:00")
        self._label_timer.setObjectName("timer_label")
        self._label_timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label_timer.hide()
        layout.addWidget(self._label_timer)

        # ── Botão hero: Iniciar / Parar ───────────────────────────────
        self._btn_start = QPushButton("▶  Iniciar Reunião")
        self._btn_start.setObjectName("btn_start")
        self._btn_start.setFixedHeight(56)
        self._btn_start.clicked.connect(self._on_start)

        self._btn_stop = QPushButton("⏹  Parar e Processar")
        self._btn_stop.setObjectName("btn_stop")
        self._btn_stop.setFixedHeight(56)
        self._btn_stop.hide()
        self._btn_stop.clicked.connect(self._on_stop)

        layout.addWidget(self._btn_start)
        layout.addWidget(self._btn_stop)
        layout.addSpacing(20)

        # ── Progresso ─────────────────────────────────────────────────
        self._label_progress = QLabel()
        self._label_progress.setObjectName("progress_label")
        self._label_progress.hide()
        layout.addWidget(self._label_progress)

        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)
        layout.addSpacing(12)

        layout.addStretch()

        # ── Separador ─────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("separator")
        layout.addWidget(sep)
        layout.addSpacing(10)

        # ── Ações secundárias: importar ───────────────────────────────
        import_row = QHBoxLayout()
        import_row.setSpacing(8)

        lbl_import = QLabel("Importar:")
        lbl_import.setObjectName("footer_label")
        import_row.addWidget(lbl_import)

        self._btn_import = QPushButton("📂  Áudio")
        self._btn_import.setObjectName("btn_secondary")
        self._btn_import.setFixedHeight(32)
        self._btn_import.clicked.connect(self._on_import_audio)
        import_row.addWidget(self._btn_import)

        self._btn_import_txt = QPushButton("📄  TXT / VTT")
        self._btn_import_txt.setObjectName("btn_secondary")
        self._btn_import_txt.setFixedHeight(32)
        self._btn_import_txt.clicked.connect(self._on_import_txt)
        import_row.addWidget(self._btn_import_txt)

        import_row.addStretch()

        self._btn_folder = QPushButton("📁  Abrir Notes")
        self._btn_folder.setObjectName("btn_secondary")
        self._btn_folder.setFixedHeight(32)
        self._btn_folder.clicked.connect(self._open_notes_folder)
        import_row.addWidget(self._btn_folder)

        self._btn_obsidian = QPushButton("🟣  Obsidian")
        self._btn_obsidian.setObjectName("btn_secondary")
        self._btn_obsidian.setFixedHeight(32)
        self._btn_obsidian.clicked.connect(self._open_in_obsidian)
        import_row.addWidget(self._btn_obsidian)

        layout.addLayout(import_row)
        layout.addSpacing(8)

        # ── Rodapé: pasta + backend ───────────────────────────────────
        footer = QHBoxLayout()
        footer.setSpacing(6)

        self._label_notes_dir = QLabel()
        self._label_notes_dir.setObjectName("footer_label")
        self._update_notes_dir_label()
        footer.addWidget(QLabel("📁"), )
        footer.addWidget(self._label_notes_dir, stretch=1)

        btn_change_dir = QPushButton("Alterar")
        btn_change_dir.setObjectName("btn_secondary")
        btn_change_dir.setFixedHeight(26)
        btn_change_dir.clicked.connect(self._on_change_notes_dir)
        footer.addWidget(btn_change_dir)

        layout.addLayout(footer)

        return tab

    def _build_agent_tab(self) -> QWidget:
        self._agent_widget = AgentWidget(self._controller)
        return self._agent_widget

    # ------------------------------------------------------------------
    # Estado da UI
    # ------------------------------------------------------------------

    def _set_state(self, state: str):
        """Transições: idle | recording | processing | done | error"""
        idle       = state == "idle"
        recording  = state == "recording"
        processing = state == "processing"
        done       = state == "done"
        error      = state == "error"

        self._btn_start.setVisible(not recording and not processing)
        self._btn_start.setEnabled(idle or done or error)
        self._btn_stop.setVisible(recording)

        self._btn_import.setEnabled(idle or done or error)
        self._btn_import_txt.setEnabled(idle or done or error)

        self._label_timer.setVisible(recording)

        show_progress = processing or done or error
        self._label_progress.setVisible(show_progress)
        self._progress_bar.setVisible(show_progress)

    # ------------------------------------------------------------------
    # Slots — Gravação
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_start(self):
        dlg = NewMeetingDialog(self._controller, parent=self)
        if dlg.exec() != NewMeetingDialog.DialogCode.Accepted:
            return

        title   = dlg.get_title()
        profile = dlg.get_profile()
        mic_device = dlg.get_mic_device_index()
        if not title:
            return

        save_mic_device_index(mic_device)

        try:
            self._controller.set_devices(mic_device, None)
            self._controller.start_meeting(title, profile)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        rec = self._controller._recorder
        audio_info = "🎤 + 🔊 mic e sistema" if rec.has_loopback else "🎤 só microfone"

        self._elapsed_seconds = 0
        self._label_timer.setText("00:00")
        self._timer.start()
        self._tray.setIcon(make_tray_icon(recording=True))
        self._tray.setToolTip(f"{APP_NAME} — Gravando")
        self._label_status.setText(f"⏺  Gravando: {title}  ({audio_info})")
        self._status_bar.showMessage(f"Gravação em andamento: {title}")
        self._set_state("recording")

    @pyqtSlot()
    def _on_stop(self):
        self._timer.stop()

        self._label_status.setText("Processando...")
        self._set_state("processing")

        try:
            self._controller.stop_recording()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao parar gravação", str(e))
            self._set_state("idle")
            self._label_status.setText("Pronto para gravar")
            return

        self._progress_bar.setValue(0)
        self._label_progress.setText("Iniciando processamento...")
        self._status_bar.showMessage("Transcrevendo e gerando resumo...")

        self._worker = ProcessingWorker(self._controller)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    # ------------------------------------------------------------------
    # Slots — Importar
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_import_audio(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar arquivo de áudio", str(Path.home()),
            "Áudio (*.wav *.mp3 *.m4a *.ogg *.flac *.mp4 *.webm)",
        )
        if not path:
            return

        audio_path    = Path(path)
        default_title = audio_path.stem.replace("-", " ").replace("_", " ")

        dlg = ImportDialog(default_title, get_last_profile(), parent=self)
        if dlg.exec() != ImportDialog.DialogCode.Accepted:
            return

        title   = dlg.get_title()
        profile = dlg.get_profile()
        if not title:
            return
        save_last_profile(profile)

        try:
            self._controller.import_audio(audio_path, title, profile)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        self._label_status.setText(f"⏳  Processando: {title}")
        self._label_progress.setText("Iniciando transcrição...")
        self._progress_bar.setValue(0)
        self._status_bar.showMessage(f"Importando áudio: {audio_path.name}")
        self._set_state("processing")

        self._worker = ProcessingWorker(self._controller)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    @pyqtSlot()
    def _on_import_txt(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar transcrição", str(Path.home()),
            "Transcrição (*.txt *.vtt)",
        )
        if not path:
            return

        txt_path      = Path(path)
        default_title = txt_path.stem.replace("-", " ").replace("_", " ")

        dlg = ImportDialog(default_title, get_last_profile(), parent=self)
        if dlg.exec() != ImportDialog.DialogCode.Accepted:
            return

        title   = dlg.get_title()
        profile = dlg.get_profile()
        if not title:
            return
        save_last_profile(profile)

        try:
            self._controller.import_txt(txt_path, title, profile)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        self._label_status.setText(f"⏳  Resumindo: {title}")
        self._label_progress.setText("Gerando resumo...")
        self._progress_bar.setValue(0)
        self._status_bar.showMessage(f"Processando: {txt_path.name}")
        self._set_state("processing")

        self._worker = TxtProcessingWorker(self._controller)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    # ------------------------------------------------------------------
    # Slots — Progresso e resultado
    # ------------------------------------------------------------------

    @pyqtSlot(str, int)
    def _on_progress(self, message: str, value: int):
        self._label_progress.setText(message)
        self._progress_bar.setValue(value)
        self._status_bar.showMessage(message)

    @pyqtSlot(str)
    def _on_finished(self, path: str):
        filename = Path(path).name
        fallback = self._controller.consume_fallback_notice()
        if fallback:
            self._label_status.setText(f"✅  Salvo (fallback): {filename}")
            self._label_progress.setText(f"⚠️ {fallback}")
            self._status_bar.showMessage(f"Concluído com fallback: {fallback}")
        else:
            self._label_status.setText(f"✅  Salvo: {filename}")
            self._label_progress.setText("Documento gerado com sucesso!")
            self._status_bar.showMessage(f"Concluído: {path}")
        self._progress_bar.setValue(100)
        self._tray.setIcon(make_tray_icon(recording=False))
        self._tray.setToolTip(APP_NAME)
        self._set_state("done")

    @pyqtSlot(str)
    def _on_error(self, message: str):
        self._label_status.setText("❌  Erro no processamento")
        self._label_progress.setText(f"Erro: {message}")
        self._status_bar.showMessage(f"Erro: {message}")
        self._tray.setIcon(make_tray_icon(recording=False))
        self._tray.setToolTip(APP_NAME)
        self._set_state("error")
        QMessageBox.critical(self, "Erro no processamento", message)

    @pyqtSlot()
    def _update_timer(self):
        self._elapsed_seconds += 1
        m, s = divmod(self._elapsed_seconds, 60)
        self._label_timer.setText(f"{m:02d}:{s:02d}")

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

    _REG_KEY  = r"Software\Microsoft\Windows\CurrentVersion\Run"
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
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._REG_KEY, 0, winreg.KEY_SET_VALUE)
        if checked:
            vbs = Path(__file__).parent.parent / "run.vbs"
            winreg.SetValueEx(key, self._REG_NAME, 0, winreg.REG_SZ, f'wscript.exe "{vbs}"')
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
    # Helpers
    # ------------------------------------------------------------------

    def _on_backend_changed(self, backend: str):
        config.SUMMARIZER_BACKEND = backend
        save_summarizer_backend(backend)
        self._controller.set_summarizer_backend(backend)
        self._check_api()

    def _check_api(self):
        summarizer = self._controller._summarizer
        backend    = summarizer.backend

        if not summarizer.is_available():
            self._label_api.setText("🔴 Chave API ausente")
            self._label_api.setStyleSheet("color: #f38ba8; font-size: 12px;")
            return

        if backend == "claude":
            from config import ANTHROPIC_MODEL
            self._label_api.setText(f"🟢 {ANTHROPIC_MODEL}")
            self._label_api.setStyleSheet("color: #a6e3a1; font-size: 12px;")
            return

        # Gemini/DeepSeek: ping real em background
        label = "Gemini" if backend == "gemini" else "DeepSeek"
        self._label_api.setText(f"🟡 Verificando {label}...")
        self._label_api.setStyleSheet("color: #f9e2af; font-size: 12px;")
        self._api_ping_thread = _ApiPingThread(summarizer)
        self._api_ping_thread.result.connect(self._on_api_ping_result)
        self._api_ping_thread.start()

    @pyqtSlot(str, bool, str)
    def _on_api_ping_result(self, backend: str, ok: bool, message: str):
        if backend != self._controller._summarizer.backend:
            return
        label = "Gemini" if backend == "gemini" else "DeepSeek"
        if ok:
            self._label_api.setText(f"🟢 {label} alcançável")
            if backend == "gemini":
                self._label_api.setToolTip(
                    "Endpoint /models respondeu OK. O generateContent pode ainda "
                    "retornar 503 — nesse caso há fallback automático."
                )
            else:
                from config import DEEPSEEK_MODEL
                self._label_api.setToolTip(f"Modelo configurado: {DEEPSEEK_MODEL}")
            self._label_api.setStyleSheet("color: #a6e3a1; font-size: 12px;")
        else:
            self._label_api.setText(f"🔴 {label} — {message}")
            self._label_api.setToolTip("")
            self._label_api.setStyleSheet("color: #f38ba8; font-size: 12px;")

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

    @pyqtSlot()
    def _open_notes_folder(self):
        import subprocess
        subprocess.Popen(["explorer", str(self._notes_dir)])

    @pyqtSlot()
    def _open_in_obsidian(self):
        import os
        import urllib.parse
        encoded = urllib.parse.quote(str(self._notes_dir), safe="")
        os.startfile(f"obsidian://open?path={encoded}")


class _ApiPingThread(QThread):
    result = pyqtSignal(str, bool, str)

    def __init__(self, summarizer):
        super().__init__()
        self._summarizer = summarizer

    def run(self):
        ok, msg = self._summarizer.ping()
        self.result.emit(self._summarizer.backend, ok, msg)
