import logging
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QFont
from qtpy.QtWidgets import QPlainTextEdit, QWidget, QVBoxLayout

logger = logging.getLogger("FuturisticEditor")

class MiniMapWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        f = QFont("Cascadia Code", 5)
        f.setLetterSpacing(QFont.PercentageSpacing, 95)
        self.view.setFont(f)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.addWidget(self.view)
        self._source = None
        self._pending = False

    def bind(self, source_editor):
        try:
            self._source = source_editor
            self.sync_text()
            source_editor.textChanged.connect(self.schedule_sync)
            source_editor.verticalScrollBar().valueChanged.connect(self.sync_scroll)
            self.view.mousePressEvent = self._jump_to_click
        except Exception as e:
            logger.error(f"[MiniMapWidget] bind erro: {e}")

    def schedule_sync(self):
        if self._pending:
            return
        self._pending = True
        QTimer.singleShot(80, self.sync_text)

    def sync_text(self):
        try:
            if not self._source:
                return
            self.view.setPlainText(self._source.toPlainText())
            self.sync_scroll()
            self._pending = False
        except Exception as e:
            logger.error(f"[MiniMapWidget] sync_text erro: {e}")
            self._pending = False

    def sync_scroll(self):
        try:
            if not self._source:
                return
            src_sb = self._source.verticalScrollBar()
            dst_sb = self.view.verticalScrollBar()
            if src_sb.maximum() == 0:
                dst_sb.setValue(0)
                return
            ratio = src_sb.value() / max(1, src_sb.maximum())
            dst_sb.setValue(int(ratio * dst_sb.maximum()))
        except Exception as e:
            logger.error(f"[MiniMapWidget] sync_scroll erro: {e}")

    def _jump_to_click(self, e):
        try:
            pos = e.pos()
            dst_sb = self.view.verticalScrollBar()
            ratio = pos.y() / max(1, self.view.height())
            dst_sb.setValue(int(ratio * dst_sb.maximum()))
            if self._source:
                src_sb = self._source.verticalScrollBar()
                src_sb.setValue(int(ratio * src_sb.maximum()))
        except Exception as e:
            logger.error(f"[MiniMapWidget] _jump_to_click erro: {e}")
