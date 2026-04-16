"""
Ícone do system tray. Usa icon.ico se disponível, senão gera um ícone simples.
"""
from pathlib import Path
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from PyQt6.QtCore import Qt

_ICON_PATH = Path(__file__).parent.parent / "icon.ico"


def make_tray_icon(recording: bool = False) -> QIcon:
    """Retorna ícone para o system tray. Overlay vermelho quando gravando."""
    if _ICON_PATH.exists() and not recording:
        return QIcon(str(_ICON_PATH))

    # Gera ícone de fallback (ou overlay de gravação)
    size = 32
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if recording:
        # Overlay vermelho pulsante para indicar gravação
        if _ICON_PATH.exists():
            base = QPixmap(str(_ICON_PATH)).scaled(size, size)
            painter.drawPixmap(0, 0, base)
        else:
            painter.setBrush(QColor("#1e88e5"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(2, 2, size - 4, size - 4)

        # Ponto vermelho no canto superior direito
        painter.setBrush(QColor("#e53935"))
        painter.setPen(Qt.PenStyle.NoPen)
        dot = 10
        painter.drawEllipse(size - dot - 1, 1, dot, dot)
    else:
        painter.setBrush(QColor("#1e88e5"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)
        painter.setPen(QPen(QColor("white")))
        from PyQt6.QtGui import QFont
        painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "M")

    painter.end()
    return QIcon(px)
