import logging
import os

from qtpy.QtWidgets import (
    QDialog, QTabWidget, QVBoxLayout, QWidget, QPlainTextEdit,
    QMenu, QShortcut
)
from qtpy.QtGui import QPainter, QColor, QKeySequence
from qtpy.QtCore import Qt, QRect, QSize

from utils.utilities import get_style_sheet, COLOR_VARS

logger = logging.getLogger("FileContentViewer")

class LineNumberArea(QWidget):
    """Widget para mostrar números de linha ao lado de um CodeEditor."""
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)


class CodeEditor(QPlainTextEdit):
    """Editor de texto com área de números de linha e edição habilitada."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)

        self.updateLineNumberAreaWidth(0)
        self.setReadOnly(False)

    def lineNumberAreaWidth(self):
        digits = len(str(self.blockCount()))
        space = 3 + self.fontMetrics().width('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(
            cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()
        ))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor(COLOR_VARS['bgdark']))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor(COLOR_VARS['accentlight']))
                painter.drawText(
                    0, int(top), self.lineNumberArea.width(),
                    self.fontMetrics().height(),
                    Qt.AlignRight, number
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1


class FileContentViewer(QDialog):
    """Diálogo com abas para visualização e edição de arquivos de texto."""
    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self.setStyleSheet(get_style_sheet())
            self.setWindowFlags(
                self.windowFlags()
                | Qt.WindowMinimizeButtonHint
                | Qt.WindowMaximizeButtonHint
            )
            self.setWindowTitle("Visualizador de Arquivos")
            self.resize(800, 600)

            self._shortcut_save = QShortcut(QKeySequence.Save, self)
            self._shortcut_save.activated.connect(self._on_save_shortcut)

            self.tabs = QTabWidget(self)
            self.tabs.setTabsClosable(True)
            self.tabs.tabCloseRequested.connect(self._close_tab)
            self.tabs.setContextMenuPolicy(Qt.CustomContextMenu)
            self.tabs.customContextMenuRequested.connect(self._tab_context_menu)

            layout = QVBoxLayout(self)
            layout.addWidget(self.tabs)
        except Exception as e:
            logger.error(f"[FileContentViewer] init error: {e}", exc_info=True)

    def add_file(self, path: str) -> None:
        """Adiciona um arquivo em nova aba, ou foca se já estiver aberta."""
        try:
            name = os.path.basename(path)
            for idx in range(self.tabs.count()):
                if self.tabs.tabText(idx) == name:
                    self.tabs.setCurrentIndex(idx)
                    return

            with open(path, "r", encoding="utf-8") as f:
                text = f.read()

            editor = CodeEditor(self)
            editor.setPlainText(text)
            editor._file_path = path

            self.tabs.addTab(editor, name)
            self.tabs.setCurrentWidget(editor)
            if not self.isVisible():
                self.show()
        except Exception as e:
            logger.error(f"[FileContentViewer] failed to open {path}: {e}", exc_info=True)

    def _save_current(self, index: int) -> None:
        """Salva o arquivo na aba especificada."""
        editor = self.tabs.widget(index)
        path = getattr(editor, '_file_path', None)
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(editor.toPlainText())
        except Exception as e:
            logger.error(f"[FileContentViewer] save error: {e}", exc_info=True)

    def _save_all(self) -> None:
        """Salva todos os arquivos abertos."""
        for idx in range(self.tabs.count()):
            editor = self.tabs.widget(idx)
            path = getattr(editor, '_file_path', None)
            if path:
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(editor.toPlainText())
                except Exception as e:
                    logger.error(f"[FileContentViewer] save_all error: {e}", exc_info=True)

    def _on_save_shortcut(self) -> None:
        idx = self.tabs.currentIndex()
        if idx >= 0:
            self._save_current(idx)

    def _tab_context_menu(self, pos):
        idx = self.tabs.tabBar().tabAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        save_current_action = menu.addAction("Salvar aba atual")
        save_all_action = menu.addAction("Salvar todos")
        global_pos = self.tabs.mapToGlobal(pos)
        action = menu.exec_(global_pos)
        if action == save_current_action:
            self._save_current(idx)
        elif action == save_all_action:
            self._save_all()

    def _close_tab(self, index: int) -> None:
        """Fecha a aba de visualização do arquivo."""
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()