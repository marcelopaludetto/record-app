"""
Diálogo de Nova Reunião — título e dispositivos de áudio.
"""
import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QDialogButtonBox, QGroupBox,
)
from PyQt6.QtCore import Qt

from core.recorder import AudioRecorder


class NewMeetingDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Nova Reunião")
        self.setMinimumWidth(420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Título ---
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        default_title = "Reunião " + datetime.datetime.now().strftime("%d/%m %H:%M")
        self._title_input = QLineEdit(default_title)
        self._title_input.selectAll()
        form.addRow("Título:", self._title_input)
        layout.addLayout(form)

        # --- Dispositivos ---
        devices_group = QGroupBox("Dispositivos de áudio")
        devices_layout = QVBoxLayout(devices_group)

        rec = self._controller._recorder
        mic_name = self._get_mic_name(rec.mic_device)
        devices_layout.addWidget(QLabel(f"🎤 Microfone: {mic_name}"))

        if rec.loopback_device is not None:
            lb_list = AudioRecorder.list_loopback_devices()
            lb_info = next((d for d in lb_list if d["index"] == rec.loopback_device), None)
            lb_name = lb_info["name"] if lb_info else str(rec.loopback_device)
            lbl = QLabel(f"🔊 Sistema (loopback): {lb_name}")
            lbl.setStyleSheet("color: #a6e3a1;")
        else:
            lbl = QLabel("🔊 Sistema (loopback): não disponível")
            lbl.setStyleSheet("color: #f38ba8;")
        devices_layout.addWidget(lbl)

        layout.addWidget(devices_group)

        # --- Botões OK/Cancelar ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._title_input.setFocus()

    def get_title(self) -> str:
        return self._title_input.text().strip()

    def _get_mic_name(self, device_index) -> str:
        try:
            import sounddevice as sd
            if device_index is None:
                return sd.query_devices(kind="input")["name"]
            return sd.query_devices(device_index)["name"]
        except Exception:
            return "padrão do sistema"
