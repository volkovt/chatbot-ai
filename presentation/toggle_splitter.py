from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QSplitter, QSplitterHandle


class ToggleHandle(QSplitterHandle):
    """Splitter handle that toggles the second panel on double-click."""
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            splitter = self.splitter()
            sizes = splitter.sizes()
            if getattr(splitter, '_saved_sizes', None) is None:
                splitter._saved_sizes = sizes.copy()
                total = sum(sizes)
                splitter.setSizes([total, 0])
            else:
                splitter.setSizes(splitter._saved_sizes)
                splitter._saved_sizes = None
        super().mouseDoubleClickEvent(event)

class ToggleSplitter(QSplitter):
    """QSplitter using ToggleHandle for interactive hide/show."""
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)

    def createHandle(self):
        return ToggleHandle(self.orientation(), self)
