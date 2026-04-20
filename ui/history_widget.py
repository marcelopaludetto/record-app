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
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Lista (esquerda) ──────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(12, 12, 6, 12)
        left_layout.setSpacing(8)

        header_row = QHBoxLayout()
        lbl = QLabel("Reuniões")
        lbl.setObjectName("section_label")
        header_row.addWidget(lbl, stretch=1)

        self._btn_refresh = QPushButton("↻")
        self._btn_refresh.setObjectName("btn_secondary")
        self._btn_refresh.setFixedSize(28, 28)
        self._btn_refresh.setToolTip("Atualizar lista")
        self._btn_refresh.clicked.connect(self._on_refresh)
        header_row.addWidget(self._btn_refresh)

        left_layout.addLayout(header_row)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self._list)
        splitter.addWidget(left)

        # ── Preview (direita) ─────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 12, 12, 12)
        right_layout.setSpacing(8)

        preview_header = QHBoxLayout()
        lbl2 = QLabel("Preview")
        lbl2.setObjectName("section_label")
        preview_header.addWidget(lbl2, stretch=1)

        self._btn_open_file = QPushButton("Abrir .md")
        self._btn_open_file.setObjectName("btn_secondary")
        self._btn_open_file.setFixedHeight(28)
        self._btn_open_file.clicked.connect(self._open_file)
        self._btn_open_file.setEnabled(False)
        preview_header.addWidget(self._btn_open_file)

        right_layout.addLayout(preview_header)

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setObjectName("preview_view")
        right_layout.addWidget(self._preview)

        splitter.addWidget(right)
        splitter.setSizes([260, 480])
        layout.addWidget(splitter)

    def load_meetings(self, meetings: list[Meeting]):
        current_row = self._list.currentRow()
        self._meetings = meetings
        self._list.clear()
        for m in meetings:
            date_str     = m.started_at.strftime("%d/%m/%Y %H:%M")
            status_icon  = {"done": "✅", "error": "❌", "recording": "⏺"}.get(m.status, "⏳")
            profile_tag  = "  [terapia]" if getattr(m, "profile", "") == "terapia" else ""
            item = QListWidgetItem(f"{status_icon}  {date_str}{profile_tag}\n   {m.title}")
            item.setData(Qt.ItemDataRole.UserRole, m.id)
            self._list.addItem(item)
        if 0 <= current_row < self._list.count():
            self._list.setCurrentRow(current_row)

    def _on_refresh(self):
        # Disparado pelo botão — re-emite request via sinal implícito:
        # a main_window conectou _on_tab_changed que já faz o load.
        # Aqui chamamos load com o que temos, ou deixamos a main_window
        # reagir ao sinal. Para simplicidade, chamamos a callback direta.
        if hasattr(self, "_refresh_callback") and self._refresh_callback:
            self._refresh_callback()

    def set_refresh_callback(self, callback):
        self._refresh_callback = callback

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._meetings):
            self._preview.clear()
            self._btn_open_file.setEnabled(False)
            return

        m = self._meetings[row]
        self.meeting_selected.emit(m)
        has_file = bool(m.output_md_path and Path(str(m.output_md_path)).exists())
        self._btn_open_file.setEnabled(has_file)
        self._preview.setMarkdown(_build_preview(m))

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
    date_str = m.started_at.strftime("%d/%m/%Y %H:%M")
    meta = f"{date_str} · {m.duration_label}"
    if getattr(m, "tipo_agenda", ""):
        meta += f" · {m.tipo_agenda}"
    lines.append(meta)

    if getattr(m, "tldr", []):
        lines.append("")
        lines.append("**Resumo**")
        for t in m.tldr:
            lines.append(f"- {t}")

    for topic in m.topics:
        lines.append("")
        lines.append(f"## {topic.title}")
        for b in topic.bullets:
            lines.append(f"- {b.text}")
            for sub in b.sub_bullets:
                lines.append(f"  - {sub}")

    if m.next_steps:
        lines.append("")
        lines.append("## Próximos Passos")
        for s in m.next_steps:
            lines.append(f"- {s.action}")

    if m.error_message:
        lines.append(f"\n⚠️ Erro: {m.error_message}")

    return "\n".join(lines)
