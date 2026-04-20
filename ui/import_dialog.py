"""
Diálogo unificado para importação de áudio ou TXT.
Coleta título e tipo em uma única janela, sem dialogs sequenciais.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLabel, QLineEdit,
    QDialogButtonBox, QHBoxLayout, QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt

from ui.meeting_dialog import PROFILE_OPTIONS


class ImportDialog(QDialog):
    def __init__(self, default_title: str, last_profile: str = "trabalho", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importar arquivo")
        self.setMinimumWidth(400)
        self._last_profile = last_profile
        self._default_title = default_title
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._title_input = QLineEdit(self._default_title)
        self._title_input.selectAll()
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
        if idx < 0:
            return self._last_profile
        return PROFILE_OPTIONS[idx][1]
