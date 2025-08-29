import logging
from PyQt5.QtCore import Qt, QPropertyAnimation, pyqtProperty, QRectF
from PyQt5.QtGui import QPainter, QLinearGradient, QColor, QFont
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

import qtawesome as qta

logger = logging.getLogger("FuturisticEditor")

class FuturisticTitleBar(QWidget):
    def __init__(self, parent=None, title="Code Editor Futurista"):
        super().__init__(parent)
        self._glow_pos = 0.0
        self.setFixedHeight(44)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._title = QLabel(title)
        self._title.setFont(QFont("Segoe UI", 10, QFont.Medium))
        self._title.setObjectName("WindowTitle")
        self._btn_min = QPushButton()
        self._btn_min.setIcon(qta.icon("fa5s.window-minimize", color="orange"))
        self._btn_max = QPushButton()
        self._btn_max.setIcon(qta.icon("fa5s.window-maximize", color="lime"))
        self._btn_close = QPushButton()
        self._btn_close.setIcon(qta.icon("fa5s.window-close", color="red"))
        for b in (self._btn_min, self._btn_max, self._btn_close):
            b.setFixedSize(28, 24)
            b.setCursor(Qt.PointingHandCursor)
        self._apply_button_style("dark")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(8)
        lay.addWidget(self._title)
        lay.addStretch(1)
        lay.addWidget(self._btn_min)
        lay.addWidget(self._btn_max)
        lay.addWidget(self._btn_close)
        self._setup_anim()
        self._wire_buttons()

    def _wire_buttons(self):
        try:
            self._btn_min.clicked.connect(lambda: self.window().showMinimized())
            self._btn_max.clicked.connect(lambda: self.window().showNormal() if self.window().isMaximized() else self.window().showMaximized())
            self._btn_close.clicked.connect(lambda: self.window().close())
        except Exception as e:
            logger.error(f"[FuturisticTitleBar] erro ao conectar botões: {e}")

    def _apply_button_style(self, theme_name: str):
        try:
            if theme_name == "dark":
                style = "QPushButton{border:1px solid rgba(255,255,255,30); border-radius:6px;} QPushButton:hover{background: rgba(255,255,255,0.08);}"
            else:
                style = "QPushButton{border:1px solid rgba(0,0,0,25); border-radius:6px;} QPushButton:hover{background: rgba(0,0,0,0.06);}"
            self._btn_min.setStyleSheet(style)
            self._btn_max.setStyleSheet(style)
            self._btn_close.setStyleSheet(style)
        except Exception as e:
            logger.error(f"[FuturisticTitleBar] _apply_button_style erro: {e}")

    def _setup_anim(self):
        try:
            self._anim = QPropertyAnimation(self, b"glowPos")
            self._anim.setStartValue(0.0)
            self._anim.setEndValue(1.0)
            self._anim.setDuration(2200)
            self._anim.setLoopCount(-1)
            self._anim.start()
        except Exception as e:
            logger.error(f"[FuturisticTitleBar] erro animação: {e}")

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing, True)
            rect = self.rect()
            grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
            grad.setColorAt(0.0, QColor(0,0,0,0))
            grad.setColorAt(max(0.0, self._glow_pos - 0.1), QColor(255,255,255,0))
            grad.setColorAt(self._glow_pos, QColor(255,255,255,38))
            grad.setColorAt(min(1.0, self._glow_pos + 0.1), QColor(255,255,255,0))
            grad.setColorAt(1.0, QColor(0,0,0,0))
            p.fillRect(QRectF(rect), grad)
        except Exception as e:
            logger.error(f"[FuturisticTitleBar] paintEvent erro: {e}")

    def mousePressEvent(self, e):
        try:
            if e.button() == Qt.LeftButton:
                self._drag_pos = e.globalPos() - self.window().frameGeometry().topLeft()
        except Exception as e:
            logger.error(f"[FuturisticTitleBar] mousePressEvent erro: {e}")

    def mouseMoveEvent(self, e):
        try:
            if e.buttons() & Qt.LeftButton:
                self.window().move(e.globalPos() - self._drag_pos)
        except Exception as e:
            logger.error(f"[FuturisticTitleBar] mouseMoveEvent erro: {e}")

    def getGlowPos(self):
        return self._glow_pos

    def setGlowPos(self, v: float):
        self._glow_pos = v
        self.update()

    def set_theme(self, theme_name: str):
        try:
            self._apply_button_style(theme_name)
            self.update()
        except Exception as e:
            logger.warning(f"[FuturisticTitleBar] set_theme erro: {e}")

    glowPos = pyqtProperty(float, fget=getGlowPos, fset=setGlowPos)
