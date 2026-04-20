"""
Widget de chat para o agente conversacional de tarefas.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QLineEdit, QPushButton, QFrame, QSizePolicy, QTextEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QTextOption


class _AutoSizeTextEdit(QTextEdit):
    """QTextEdit que ajusta a altura ao conteúdo automaticamente."""

    def sizeHint(self) -> QSize:
        self.document().setTextWidth(self.viewport().width() or 700)
        h = int(self.document().size().height()) + 24
        return QSize(super().sizeHint().width(), h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateGeometry()

from core.meeting_agent import MeetingAgent
from core.meeting_controller import MeetingController


class _AskWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, agent: MeetingAgent, message: str, controller: MeetingController):
        super().__init__()
        self._agent = agent
        self._message = message
        self._controller = controller

    def run(self):
        try:
            meetings = self._controller.list_meetings(limit=50)
            reply = self._agent.ask(self._message, meetings)
            self.finished.emit(reply)
        except Exception as exc:
            self.error.emit(str(exc))


def _make_bubble(text: str, is_user: bool) -> QWidget:
    """Cria uma bolha de mensagem estilizada."""
    wrapper = QWidget()
    wrapper_layout = QHBoxLayout(wrapper)
    wrapper_layout.setContentsMargins(8, 4, 8, 4)

    font = QFont("Segoe UI", 13)

    if is_user:
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        bubble.setMaximumWidth(480)
        bubble.setFont(font)
        bubble.setStyleSheet(
            "background-color: #1e66f5; color: #ffffff;"
            "border-radius: 12px; padding: 8px 12px;"
        )
        wrapper_layout.addStretch()
        wrapper_layout.addWidget(bubble)
    else:
        bubble = _AutoSizeTextEdit()
        bubble.setReadOnly(True)
        bubble.setMarkdown(text)
        bubble.setWordWrapMode(QTextOption.WrapMode.WordWrap)
        bubble.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        bubble.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        bubble.setFrameShape(QFrame.Shape.NoFrame)
        bubble.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bubble.setFont(font)
        bubble.setStyleSheet(
            "background-color: #313244; color: #cdd6f4;"
            "border-radius: 12px; padding: 10px 14px;"
        )
        wrapper_layout.addWidget(bubble)

    return wrapper


class AgentWidget(QWidget):
    def __init__(self, controller: MeetingController, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._agent = MeetingAgent()
        self._worker: _AskWorker | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        # Área de scroll com as mensagens
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._chat_container = QWidget()
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setSpacing(4)
        self._chat_layout.addStretch()

        self._scroll.setWidget(self._chat_container)
        layout.addWidget(self._scroll, stretch=1)

        # Mensagem inicial
        self._add_bubble(
            "Olá! Pergunte sobre suas tarefas, reuniões ou próximos passos. "
            "Ex: 'Quais são minhas tarefas mais importantes?'",
            is_user=False,
        )

        # Linha de input
        input_row = QHBoxLayout()
        input_row.setSpacing(8)
        input_row.setContentsMargins(8, 0, 8, 8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Digite sua pergunta...")
        self._input.setFixedHeight(38)
        self._input.returnPressed.connect(self._on_send)

        self._btn_send = QPushButton("Enviar")
        self._btn_send.setFixedHeight(38)
        self._btn_send.setMinimumWidth(80)
        self._btn_send.clicked.connect(self._on_send)

        self._btn_clear = QPushButton("Limpar")
        self._btn_clear.setFixedHeight(38)
        self._btn_clear.setMinimumWidth(70)
        self._btn_clear.clicked.connect(self._on_clear)

        input_row.addWidget(self._input, stretch=1)
        input_row.addWidget(self._btn_send)
        input_row.addWidget(self._btn_clear)
        layout.addLayout(input_row)

    def _add_bubble(self, text: str, is_user: bool):
        # Insere antes do stretch (último item)
        stretch_index = self._chat_layout.count() - 1
        bubble = _make_bubble(text, is_user)
        self._chat_layout.insertWidget(stretch_index, bubble)
        QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    def _on_send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return

        self._input.clear()
        self._add_bubble(text, is_user=True)
        self._set_loading(True)

        self._worker = _AskWorker(self._agent, text, self._controller)
        self._worker.finished.connect(self._on_reply)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_reply(self, reply: str):
        self._worker = None
        self._set_loading(False)
        self._add_bubble(reply, is_user=False)

    def _on_error(self, message: str):
        self._worker = None
        self._set_loading(False)
        self._add_bubble(f"Erro: {message}", is_user=False)

    def _on_clear(self):
        self._agent.clear_history()
        # Remove todas as bolhas (exceto o stretch)
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._add_bubble(
            "Conversa reiniciada. Como posso ajudar?",
            is_user=False,
        )

    def _set_loading(self, loading: bool):
        self._btn_send.setEnabled(not loading)
        self._input.setEnabled(not loading)
        if loading:
            self._btn_send.setText("...")
        else:
            self._btn_send.setText("Enviar")
