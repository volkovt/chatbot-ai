import logging
from qtpy.QtCore import Qt, QRectF
from qtpy.QtGui import QPainter, QColor
from qtpy.QtWidgets import QWidget, QVBoxLayout

from presentation.editor.titlebar import FuturisticTitleBar

logger = logging.getLogger("FuturisticEditor")

class RoundedFramelessWindow(QWidget):
    def __init__(self, central_widget: QWidget, title="Code Editor Futurista", radius=14):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Window)
        self._theme_name = "dark"
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._radius = radius
        self._titlebar = FuturisticTitleBar(self, title)
        self._central = central_widget
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)
        root.addWidget(self._titlebar)
        root.addWidget(self._central, 1)
        self.resize(1100, 720)

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            bg = QColor(16, 18, 24, 255) if self._theme_name == "dark" else QColor(255, 255, 255, 255)
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            rect = self.rect().adjusted(2, 2, -2, -2)
            p.drawRoundedRect(QRectF(rect), self._radius, self._radius)
        except Exception as e:
            logger.error(f"[RoundedFramelessWindow] paintEvent erro: {e}")

    def set_theme(self, theme_name: str):
        try:
            self._theme_name = theme_name
            if hasattr(self._titlebar, "set_theme"):
                self._titlebar.set_theme(theme_name)
            self.update()
        except Exception as e:
            logger.warning(f"[RoundedFramelessWindow] set_theme erro: {e}")