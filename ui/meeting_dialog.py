"""
Diálogo de Nova Reunião — título, perfil e dispositivos de áudio com medidores ao vivo.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QDialogButtonBox, QGroupBox,
    QHBoxLayout, QRadioButton, QButtonGroup, QComboBox, QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer

from core.recorder import AudioRecorder
from storage.settings import (
    get_last_profile, save_last_profile,
    get_mic_device_index, get_loopback_device_index,
)
from ui.level_sampler import LevelSampler


PROFILE_OPTIONS = [
    ("Trabalho",  "trabalho"),
    ("Terapia",   "terapia"),
    ("Curso",     "curso"),
]

_METER_STYLE = """
QProgressBar {
    border: 1px solid #45475a;
    border-radius: 3px;
    background: #1e1e2e;
    height: 12px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #a6e3a1, stop:0.7 #a6e3a1, stop:1 #f38ba8);
    border-radius: 2px;
}
"""


class NewMeetingDialog(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._controller = controller
        self.setWindowTitle("Nova Reunião")
        self.setMinimumWidth(460)
        self._last_profile = get_last_profile()

        self._mic_sampler = LevelSampler()
        self._loopback_sampler = LevelSampler()
        self._loopback_devices: list[dict] = AudioRecorder.list_loopback_devices()

        self._setup_ui()

        # Timer para atualizar medidores (80ms)
        self._meter_timer = QTimer(self)
        self._meter_timer.setInterval(80)
        self._meter_timer.timeout.connect(self._update_meters)
        self._meter_timer.start()

        # Inicia samplers com dispositivos iniciais
        self._restart_mic_sampler()
        self._restart_loopback_sampler()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

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
        devices_layout.setSpacing(8)

        # Microfone: dropdown + medidor
        mic_row = QHBoxLayout()
        mic_row.setSpacing(8)
        mic_row.addWidget(QLabel("🎤 Microfone:"))

        self._combo_mic = QComboBox()
        mic_devices = AudioRecorder.list_mic_devices()
        self._mic_device_map: dict[int, int | None] = {}

        self._combo_mic.addItem("(padrão) Padrão do sistema", None)
        self._mic_device_map[0] = None

        current_mic = get_mic_device_index()
        selected_idx = 0
        for i, dev in enumerate(mic_devices, start=1):
            self._combo_mic.addItem(f"[{dev['index']}] {dev['name']}", dev["index"])
            self._mic_device_map[i] = dev["index"]
            if dev["index"] == current_mic:
                selected_idx = i

        self._combo_mic.setCurrentIndex(selected_idx)
        self._combo_mic.currentIndexChanged.connect(self._on_mic_changed)
        mic_row.addWidget(self._combo_mic, stretch=1)

        self._meter_mic = QProgressBar()
        self._meter_mic.setRange(0, 100)
        self._meter_mic.setValue(0)
        self._meter_mic.setFixedWidth(80)
        self._meter_mic.setFixedHeight(14)
        self._meter_mic.setTextVisible(False)
        self._meter_mic.setStyleSheet(_METER_STYLE)
        mic_row.addWidget(self._meter_mic)

        devices_layout.addLayout(mic_row)

        # Loopback: dropdown + medidor
        lb_row = QHBoxLayout()
        lb_row.setSpacing(8)
        lb_row.addWidget(QLabel("🔊 Sistema:"))

        self._combo_loopback = QComboBox()
        self._loopback_device_map: dict[int, int | None] = {}

        self._combo_loopback.addItem("(nenhum)", None)
        self._loopback_device_map[0] = None

        current_lb = get_loopback_device_index()
        default_lb = AudioRecorder.get_default_loopback()
        default_lb_index = default_lb["index"] if default_lb else None

        selected_lb_idx = 0
        for i, dev in enumerate(self._loopback_devices, start=1):
            self._combo_loopback.addItem(f"[{dev['index']}] {dev['name']}", dev["index"])
            self._loopback_device_map[i] = dev["index"]
            # Preferência: salvo → padrão do sistema
            if current_lb is not None and dev["index"] == current_lb:
                selected_lb_idx = i
            elif current_lb is None and dev["index"] == default_lb_index and selected_lb_idx == 0:
                selected_lb_idx = i

        self._combo_loopback.setCurrentIndex(selected_lb_idx)
        self._combo_loopback.currentIndexChanged.connect(self._on_loopback_changed)
        lb_row.addWidget(self._combo_loopback, stretch=1)

        self._meter_loopback = QProgressBar()
        self._meter_loopback.setRange(0, 100)
        self._meter_loopback.setValue(0)
        self._meter_loopback.setFixedWidth(80)
        self._meter_loopback.setFixedHeight(14)
        self._meter_loopback.setTextVisible(False)
        self._meter_loopback.setStyleSheet(_METER_STYLE)
        lb_row.addWidget(self._meter_loopback)

        devices_layout.addLayout(lb_row)
        layout.addWidget(devices_group)

        # --- Botões OK/Cancelar ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._title_input.setFocus()

    # ------------------------------------------------------------------
    # Samplers
    # ------------------------------------------------------------------

    def _restart_mic_sampler(self):
        device_index = self._mic_device_map.get(self._combo_mic.currentIndex())
        self._mic_sampler.start_mic(device_index)

    def _restart_loopback_sampler(self):
        lb_idx = self._loopback_device_map.get(self._combo_loopback.currentIndex())
        if lb_idx is None:
            self._loopback_sampler.stop()
            return
        dev_info = next((d for d in self._loopback_devices if d["index"] == lb_idx), None)
        if dev_info:
            self._loopback_sampler.start_loopback(
                lb_idx, dev_info["rate"], dev_info["channels"]
            )

    def _on_mic_changed(self, _idx: int):
        self._restart_mic_sampler()

    def _on_loopback_changed(self, _idx: int):
        self._restart_loopback_sampler()

    def _update_meters(self):
        self._meter_mic.setValue(self._mic_sampler.level)
        self._meter_loopback.setValue(self._loopback_sampler.level)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def done(self, result: int):
        self._meter_timer.stop()
        self._mic_sampler.stop()
        self._loopback_sampler.stop()
        super().done(result)

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------

    def get_title(self) -> str:
        return self._title_input.text().strip()

    def get_profile(self) -> str:
        idx = self._profile_group.checkedId()
        profile = PROFILE_OPTIONS[idx][1]
        save_last_profile(profile)
        return profile

    def get_mic_device_index(self) -> int | None:
        return self._mic_device_map.get(self._combo_mic.currentIndex())

    def get_loopback_device_index(self) -> int | None:
        return self._loopback_device_map.get(self._combo_loopback.currentIndex())
