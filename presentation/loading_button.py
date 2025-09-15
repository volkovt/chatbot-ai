import logging

from qtpy.QtCore import Qt, QTimer, QSize
from qtpy.QtGui import QPainter, QPen, QConicalGradient, QColor, QIcon
from qtpy.QtWidgets import QPushButton

logger = logging.getLogger("LoadingButton")

class LoadingButton(QPushButton):
    def __init__(self, text: str = "", tooltip="", parent=None, icon=None,
                 spinner_size: int = 16, spinner_thickness: int = 2,
                 colors=("#FF4081", "#7C4DFF")):
        super().__init__(text, parent)
        self._orig_hint: QSize = super().sizeHint()
        try:
            if icon:
                self._default_icon = icon
                self.setIcon(icon)
            else:
                self._default_icon = self.icon()

            self.setToolTip(tooltip)
            self._spinner_size = spinner_size
            self._spinner_thickness = spinner_thickness
            self._colors = colors
            self._loading = False
            self._angle = 0

            self._timer = QTimer(self)
            self._timer.setInterval(30)
            self._timer.timeout.connect(self._on_timeout)
        except Exception as e:
            logger.error(f"[LoadingButton] init error: {e}", exc_info=True)

    def setLoading(self, loading: bool):
        try:
            if loading:
                self._loading = True
                super().setEnabled(False)
                self.setIcon(QIcon())
                self._timer.start()
            else:
                self._timer.stop()
                self._loading = False
                super().setEnabled(True)
                self.setIcon(self._default_icon)
                self.update()
        except Exception as e:
            logger.error(f"[LoadingButton] setLoading failed: {e}", exc_info=True)

    def _on_timeout(self):
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        try:
            super().paintEvent(event)
            if self._loading:
                painter = QPainter(self)
                painter.setRenderHint(QPainter.Antialiasing)

                w = self.width()
                h = self.height()
                size = self._spinner_size
                x = (w - size) // 2
                y = (h - size) // 2

                grad = QConicalGradient(x + size / 2, y + size / 2, -self._angle)
                grad.setColorAt(0.0, QColor(self._colors[0]))
                grad.setColorAt(0.5, QColor(self._colors[1]))
                grad.setColorAt(1.0, QColor(self._colors[0]))

                pen = QPen(grad, self._spinner_thickness)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                painter.drawArc(x, y, size, size, 1 * 16, 320 * 16)
        except Exception as e:
            logger.error(f"[LoadingButton] paintEvent error: {e}", exc_info=True)


    def sizeHint(self):
        hint = super().sizeHint()
        if self._loading:
            return self._orig_hint
        return hint

    def minimumSizeHint(self):
        hint = super().minimumSizeHint()
        if self._loading:
            return self._orig_hint
        return hint