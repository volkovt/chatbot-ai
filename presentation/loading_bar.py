import logging

from PyQt5.QtCore import (
    Qt,
    pyqtProperty,
    QTimer,
)
from PyQt5.QtGui import (
    QPainter,
    QPen,
    QLinearGradient,
    QColor,
)
from PyQt5.QtWidgets import (
    QWidget,
    QSizePolicy,
)

logger = logging.getLogger("FuturisticLoadingBar")


class FuturisticLoadingBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self.setFixedHeight(4)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            self._offset = 0.0

            # Timer para animação (≈33fps)
            self._timer = QTimer(self)
            self._timer.setInterval(30)
            self._timer.timeout.connect(self._on_timeout)

            # Escondida por padrão
            self.hide()
        except Exception as e:
            logger.error(f"[FuturisticLoadingBar] erro na init: {e}", exc_info=True)

    def _on_timeout(self):
        try:
            # incrementa e reinicia de 1.0 → 0.0
            self._offset += 0.02
            if self._offset >= 1.0:
                self._offset -= 1.0
            self.update()
        except Exception as e:
            logger.error(f"[FuturisticLoadingBar] erro no timeout: {e}", exc_info=True)

    def start(self):
        try:
            self._timer.start()
            self.show()
        except Exception as e:
            logger.error(f"[FuturisticLoadingBar] falha ao iniciar: {e}", exc_info=True)

    def stop(self):
        try:
            self._timer.stop()
            self.hide()
        except Exception as e:
            logger.error(f"[FuturisticLoadingBar] falha ao parar: {e}", exc_info=True)

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            w = self.width()
            h = self.height()
            y = h // 2  # inteiro evita TypeError :contentReference[oaicite:2]{index=2}

            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt((self._offset + 0.0) % 1.0, QColor("#FF4081"))
            grad.setColorAt((self._offset + 0.5) % 1.0, QColor("#7C4DFF"))
            grad.setColorAt((self._offset + 1.0) % 1.0, QColor("#FF4081"))

            pen = QPen(grad, h)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(0, y, w, y)
        except Exception as e:
            logger.error(f"[FuturisticLoadingBar] erro no paintEvent: {e}", exc_info=True)
