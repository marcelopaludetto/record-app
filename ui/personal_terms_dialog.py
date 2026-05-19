from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

import config


class PersonalTermsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Termos de transcrição")
        self.setMinimumSize(720, 560)
        self._terms = config.load_personal_terms()
        self._setup_ui()
        self._load_terms()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Prompt do Whisper/Groq")
        title.setObjectName("status_label")
        layout.addWidget(title)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setMinimumHeight(96)
        layout.addWidget(self._prompt_edit)

        term_row = QHBoxLayout()
        self._term_input = QLineEdit()
        self._term_input.setPlaceholderText("Adicionar termo ao prompt, ex: Alura Start")
        self._term_input.returnPressed.connect(self._add_prompt_term)
        term_row.addWidget(self._term_input, stretch=1)

        btn_add_term = QPushButton("Adicionar termo")
        btn_add_term.clicked.connect(self._add_prompt_term)
        term_row.addWidget(btn_add_term)
        layout.addLayout(term_row)

        alias_title = QLabel("Correções rápidas")
        alias_title.setObjectName("status_label")
        layout.addWidget(alias_title)

        add_alias_row = QHBoxLayout()
        self._alias_input = QLineEdit()
        self._alias_input.setPlaceholderText("Como aparece, ex: Lis")
        add_alias_row.addWidget(self._alias_input)

        self._canonical_input = QLineEdit()
        self._canonical_input.setPlaceholderText("Corrigir para, ex: Lizandra")
        self._canonical_input.returnPressed.connect(self._add_alias)
        add_alias_row.addWidget(self._canonical_input)

        self._no_wikilink = QCheckBox("Sem wikilink")
        self._no_wikilink.setToolTip("Salva com * no final para corrigir sem criar [[wikilink]].")
        add_alias_row.addWidget(self._no_wikilink)

        btn_add_alias = QPushButton("Adicionar")
        btn_add_alias.clicked.connect(self._add_alias)
        add_alias_row.addWidget(btn_add_alias)
        layout.addLayout(add_alias_row)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filtrar:"))
        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Buscar alias ou forma correta")
        self._filter_input.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter_input, stretch=1)

        btn_remove = QPushButton("Remover selecionado")
        btn_remove.clicked.connect(self._remove_selected)
        filter_row.addWidget(btn_remove)
        layout.addLayout(filter_row)

        self._aliases_table = QTableWidget(0, 2)
        self._aliases_table.setHorizontalHeaderLabels(["Como aparece", "Corrigir para"])
        self._aliases_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._aliases_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._aliases_table.verticalHeader().setVisible(False)
        self._aliases_table.verticalHeader().setDefaultSectionSize(32)
        self._aliases_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._aliases_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._aliases_table.setAlternatingRowColors(True)
        self._aliases_table.setShowGrid(False)
        self._aliases_table.setWordWrap(False)
        layout.addWidget(self._aliases_table, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_terms(self):
        self._prompt_edit.setPlainText(str(self._terms.get("whisper_prompt", "")))
        aliases = self._terms.get("name_aliases") or {}
        for alias, canonical in aliases.items():
            self._append_alias_row(str(alias), str(canonical))

    def _add_prompt_term(self):
        term = self._term_input.text().strip()
        if not term:
            return

        prompt = self._prompt_edit.toPlainText().strip()
        if term.lower() in prompt.lower():
            self._term_input.clear()
            return

        if not prompt:
            prompt = (
                "Transcrição de reuniões em português do Brasil. "
                f"Podem aparecer estes termos e grafias: {term}."
            )
        else:
            prompt = prompt.rstrip()
            if prompt.endswith("."):
                prompt = prompt[:-1]
            prompt = f"{prompt}, {term}."

        self._prompt_edit.setPlainText(prompt)
        self._term_input.clear()

    def _add_alias(self):
        alias = self._alias_input.text().strip()
        canonical = self._canonical_input.text().strip()
        if not alias or not canonical:
            return

        if self._no_wikilink.isChecked() and not canonical.endswith("*"):
            canonical = f"{canonical}*"

        existing_row = self._find_alias_row(alias)
        if existing_row is None:
            self._append_alias_row(alias, canonical)
        else:
            self._aliases_table.setItem(existing_row, 1, QTableWidgetItem(canonical))

        self._alias_input.clear()
        self._canonical_input.clear()
        self._no_wikilink.setChecked(False)
        self._alias_input.setFocus()
        self._apply_filter()

    def _append_alias_row(self, alias: str, canonical: str):
        row = self._aliases_table.rowCount()
        self._aliases_table.insertRow(row)
        self._aliases_table.setItem(row, 0, QTableWidgetItem(alias))
        self._aliases_table.setItem(row, 1, QTableWidgetItem(canonical))

    def _find_alias_row(self, alias: str) -> int | None:
        target = alias.lower()
        for row in range(self._aliases_table.rowCount()):
            item = self._aliases_table.item(row, 0)
            if item and item.text().strip().lower() == target:
                return row
        return None

    def _remove_selected(self):
        row = self._aliases_table.currentRow()
        if row >= 0:
            self._aliases_table.removeRow(row)

    def _apply_filter(self):
        query = self._filter_input.text().strip().lower()
        for row in range(self._aliases_table.rowCount()):
            alias = self._cell_text(row, 0).lower()
            canonical = self._cell_text(row, 1).lower()
            self._aliases_table.setRowHidden(row, bool(query and query not in alias and query not in canonical))

    def _save(self):
        aliases: dict[str, str] = {}
        for row in range(self._aliases_table.rowCount()):
            alias = self._cell_text(row, 0)
            canonical = self._cell_text(row, 1)
            if alias and canonical:
                aliases[alias] = canonical

        data = {
            "whisper_prompt": self._prompt_edit.toPlainText().strip(),
            "name_aliases": aliases,
        }
        try:
            config.save_personal_terms(data)
        except Exception as exc:
            QMessageBox.critical(self, "Erro ao salvar", str(exc))
            return

        self.accept()

    def _cell_text(self, row: int, column: int) -> str:
        item = self._aliases_table.item(row, column)
        return item.text().strip() if item else ""
