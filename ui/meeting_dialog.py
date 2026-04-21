"""
Diálogo de Nova Reunião — título, perfil e dispositivos de áudio.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QDialogButtonBox, QGroupBox,
    QHBoxLayout, QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt

from core.recorder import AudioRecorder
from storage.settings import get_last_profile, save_last_profile


PROFILE_OPTIONS = [
    ("Trabalho",  "trabalho"),
    ("Terapia",   "terapia"),
]


class NewMeetingDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Nova Reunião")
        self.setMinimumWidth(420)
        self._last_profile = get_last_profile()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Título e Perfil ---
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Ex: 1:1 com Alana")
        form.addRow("Título:", self._title_input)

        self._profile_group = QButtonGroup(self)
        radio_layout = QHBoxLayout()
        radio_layout.setSpacing(16)
        for i, (label, value) in enumerate(PROFILE_OPTIONS):
            rb = QRadioButton(label)
            if value == self._last_profile:
                rb.setChecked(True)
            self._profile_group.addButton(rb, i)
            radio_layout.addWidget(rb)
        radio_layout.addStretch()
        form.addRow("Tipo:", radio_layout)

        layout.addLayout(form)

        # --- Dispositivos ---
        devices_group = QGroupBox("Dispositivos de áudio")
        devices_layout = QVBoxLayout(devices_group)

        rec = self._controller._recorder
        mic_name = self._get_mic_name(rec.mic_device)
        devices_layout.addWidget(QLabel(f"🎤 Microfone: {mic_name}"))

        loopback_name = None
        if rec.loopback_device is not None:
            lb_list = AudioRecorder.list_loopback_devices()
            lb_info = next((d for d in lb_list if d["index"] == rec.loopback_device), None)
            loopback_name = lb_info["name"] if lb_info else str(rec.loopback_device)
        else:
            default = AudioRecorder.get_default_loopback()
            if default:
                loopback_name = default["name"]

        if loopback_name:
            lbl = QLabel(f"🔊 Sistema (loopback): {loopback_name}")
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

    def get_profile(self) -> str:
        idx = self._profile_group.checkedId()
        profile = PROFILE_OPTIONS[idx][1]
        save_last_profile(profile)
        return profile

    def _get_mic_name(self, device_index) -> str:
        try:
            import sounddevice as sd
            if device_index is None:
                return sd.query_devices(kind="input")["name"]
            return sd.query_devices(device_index)["name"]
        except Exception:
            return "padrão do sistema"
