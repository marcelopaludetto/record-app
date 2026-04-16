import subprocess
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QTextEdit, QLabel, QPushButton, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal

from storage.models import Meeting


class HistoryWidget(QWidget):
    meeting_selected = pyqtSignal(Meeting)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._meetings: list[Meeting] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Reuniões gravadas:"))
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self._list)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(QLabel("Preview:"))
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        right_layout.addWidget(self._preview)

        btn_row = QHBoxLayout()
        self._btn_open_file = QPushButton("Abrir documento .md")
        self._btn_open_file.clicked.connect(self._open_file)
        self._btn_open_file.setEnabled(False)
        btn_row.addWidget(self._btn_open_file)
        right_layout.addLayout(btn_row)

        splitter.addWidget(right)
        splitter.setSizes([250, 450])
        layout.addWidget(splitter)

    def load_meetings(self, meetings: list[Meeting]):
        self._meetings = meetings
        self._list.clear()
        for m in meetings:
            date_str = m.started_at.strftime("%d/%m/%Y %H:%M")
            status_icon = {"done": "✅", "error": "❌", "recording": "⏺"}.get(m.status, "⏳")
            item = QListWidgetItem(f"{status_icon} {date_str}  —  {m.title}")
            item.setData(Qt.ItemDataRole.UserRole, m.id)
            self._list.addItem(item)

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._meetings):
            self._preview.clear()
            self._btn_open_file.setEnabled(False)
            return

        m = self._meetings[row]
        self.meeting_selected.emit(m)
        self._btn_open_file.setEnabled(bool(m.output_md_path and Path(str(m.output_md_path)).exists()))
        self._preview.setPlainText(_build_preview(m))

    def _open_file(self):
        row = self._list.currentRow()
        if row < 0 or row >= len(self._meetings):
            return
        m = self._meetings[row]
        if m.output_md_path and Path(str(m.output_md_path)).exists():
            subprocess.Popen(["explorer", str(m.output_md_path)], shell=True)


def _build_preview(m: Meeting) -> str:
    lines = []
    lines.append(f"# {m.title}")
    lines.append(f"{m.started_at.strftime('%d/%m/%Y %H:%M')} · {m.duration_label}")
    lines.append("")

    for topic in m.topics:
        lines.append(f"## {topic.title}")
        for b in topic.bullets:
            lines.append(f"* {b.text}")
            for sub in b.sub_bullets:
                lines.append(f"   * {sub}")
        lines.append("")

    if m.next_steps:
        lines.append("## Próximos Passos")
        for s in m.next_steps:
            lines.append(f"* {s.action}")

    if m.error_message:
        lines.append(f"\n⚠️ Erro: {m.error_message}")

    return "\n".join(lines)
