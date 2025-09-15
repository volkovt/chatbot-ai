import logging
from qtpy.QtCore import Qt
from qtpy.QtGui import QFont, QTextCursor, QColor, QTextFormat
from qtpy.QtWidgets import QWidget, QPlainTextEdit, QVBoxLayout, QFileDialog, QMessageBox, QShortcut, QInputDialog, \
    QTextEdit

from presentation.editor.find_replace import FindReplaceBar
from presentation.editor.syntax import PygmentsHighlighter, detect_language

logger = logging.getLogger("CodeEditor")

try:
    HAS_QSCI = True
except Exception:
    HAS_QSCI = False

PAIRS = {
    "(": ")",
    "[": "]",
    "{": "}",
    "\"": "\"",
    "'": "'"
}

LANG_KEYWORDS = {
    "python": ["def", "class", "import", "from", "return", "with", "as", "if", "elif", "else", "for", "while", "try", "except", "yield", "await", "async"],
    "javascript": ["function", "const", "let", "var", "return", "if", "else", "for", "while", "try", "catch", "await", "async", "class", "import", "export"],
    "java": ["class", "public", "private", "protected", "void", "static", "final", "return", "if", "else", "for", "while", "try", "catch", "import", "package"],
    "html": ["html", "head", "body", "div", "span", "script", "link", "meta", "style"],
    "json": [],
    "markdown": []
}

class PlainCodeEditor(QPlainTextEdit):
    def __init__(self, language="python", parent=None):
        super().__init__(parent)
        self._language = language
        self._file_path = None
        self._dirty = False

        try:
            self._highlighter = PygmentsHighlighter(self.document(), language)
            self.setFont(QFont("Cascadia Code", 11))
            self.cursorPositionChanged.connect(self._highlight_current_line)
            self.textChanged.connect(self._on_text_change)
            self._find_bar = FindReplaceBar(self)
            self._find_bar.hide()
            self._line_highlight()
            self.cursorPositionChanged.connect(self._update_current_line_highlight)
            self._update_current_line_highlight()
            self._install_shortcuts()
        except Exception as e:
            logger.error(f"[PlainCodeEditor] __init__ erro: {e}")

    def _install_shortcuts(self):
        try:
            from qtpy.QtWidgets import QShortcut
            from qtpy.QtGui import QKeySequence
            QShortcut(QKeySequence("Ctrl+F"), self, member=self.toggle_find)
            QShortcut(QKeySequence("Ctrl+H"), self, member=self.toggle_find)
            QShortcut(QKeySequence("Ctrl+G"), self, member=self.goto_line)
            QShortcut(QKeySequence.ZoomIn, self, member=self.zoom_in)
            QShortcut(QKeySequence.ZoomOut, self, member=self.zoom_out)
            QShortcut(QKeySequence("Ctrl+0"), self, member=self.zoom_reset)
        except Exception as e:
            logger.error(f"[PlainCodeEditor] erro ao instalar atalhos: {e}")

    def goto_line(self):
        try:
            line, ok = QInputDialog.getInt(self, "Ir para linha", "Número da linha:", 1, 1,
                                           self.document().blockCount())
            if ok:
                cursor = QTextCursor(self.document().findBlockByNumber(line - 1))
                self.setTextCursor(cursor)
                self.centerCursor()
        except Exception as e:
            logger.error(f"[PlainCodeEditor] goto_line erro: {e}")

    def _prompt_goto_line(self):
        try:
            from qtpy.QtWidgets import QInputDialog
            line, ok = QInputDialog.getInt(self, "Ir para linha", "Número da linha:", 1, 1, 999999, 1)
            if ok:
                self.goto_line()
        except Exception as e:
            logger.error(f"[PlainCodeEditor] _prompt_goto_line erro: {e}")

    def _update_current_line_highlight(self):
        """
        Usa QTextEdit.ExtraSelection (não self.ExtraSelection).
        Funciona tanto em QPlainTextEdit quanto em QTextEdit.
        """
        try:
            extra_selections = []

            if not self.isReadOnly():
                selection = QTextEdit.ExtraSelection()
                line_color = QColor(80, 80, 120, 50)
                selection.format.setBackground(line_color)
                selection.format.setProperty(0x0100, True)
                selection.cursor = self.textCursor()
                selection.cursor.clearSelection()
                extra_selections.append(selection)

            self.setExtraSelections(extra_selections)
        except Exception as e:
            logger.error(f"[PlainCodeEditor] _line_highlight erro: {e}")

    def toggle_find(self):
        try:
            if self._find_bar.isVisible():
                self._find_bar.hide()
            else:
                self._find_bar.attach_to_editor(self)
                self._find_bar.show()
                self._find_bar.find_edit.setFocus()
        except Exception as e:
            logger.error(f"[PlainCodeEditor] toggle_find erro: {e}")

    def keyPressEvent(self, e):
        try:
            if e.key() == Qt.Key_Return or e.key() == Qt.Key_Enter:
                cur = self.textCursor()
                cur.select(QTextCursor.LineUnderCursor)
                line_text = cur.selectedText()
                indent = ""
                for ch in line_text:
                    if ch in [" ", "\t"]:
                        indent += ch
                    else:
                        break
                super().keyPressEvent(e)
                super().insertPlainText(indent)
                return
            if e.text() in PAIRS:
                cur = self.textCursor()
                super().keyPressEvent(e)
                super().insertPlainText(PAIRS[e.text()])
                cur.movePosition(QTextCursor.Left)
                self.setTextCursor(cur)
                return
            super().keyPressEvent(e)
        except Exception as ex:
            logger.error(f"[PlainCodeEditor] keyPressEvent erro: {ex}")

    def wheelEvent(self, e):
        try:
            if e.modifiers() & Qt.ControlModifier:
                if e.angleDelta().y() > 0:
                    self.zoom_in()
                else:
                    self.zoom_out()
                e.accept()
                return
            super().wheelEvent(e)
        except Exception as ex:
            logger.error(f"[PlainCodeEditor] wheelEvent erro: {ex}")

    def _line_highlight(self):
        try:
            sel = QTextEdit.ExtraSelection()
            color = QColor(38, 79, 120, 40)
            sel.format.setBackground(color)
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            self.setExtraSelections([sel])
        except Exception as e:
            logger.error(f"[PlainCodeEditor] _line_highlight erro: {e}")

    def _highlight_current_line(self):
        self._line_highlight()

    def _on_text_change(self):
        self._dirty = True

    def set_language(self, lang: str):
        try:
            self._language = lang
            self._highlighter.set_language(lang)
            logger.info(f"[PlainCodeEditor] linguagem definida: {lang}")
        except Exception as e:
            logger.error(f"[PlainCodeEditor] set_language erro: {e}")

    def set_text(self, text=""):
        try:
            self.setPlainText(text)
            self._dirty = False
        except Exception as e:
            logger.error(f"[PlainCodeEditor] set_text erro: {e}")

    def get_text(self) -> str:
        try:
            return self.toPlainText()
        except Exception as e:
            logger.error(f"[PlainCodeEditor] get_text erro: {e}")
            return ""

    def open_file(self, path: str = None):
        try:
            if not path:
                path, _ = QFileDialog.getOpenFileName(self, "Abrir arquivo")
                if not path:
                    return
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()
            self.set_text(data)
            self._file_path = path
            self.set_language(detect_language(path, self._language))
            logger.info(f"[PlainCodeEditor] arquivo aberto: {path}")
        except Exception as e:
            logger.error(f"[PlainCodeEditor] open_file erro: {e}")
            QMessageBox.critical(self, "Erro", f"Falha ao abrir arquivo:\n{e}")

    def save_file(self, path: str = None):
        try:
            if not path and not self._file_path:
                path, _ = QFileDialog.getSaveFileName(self, "Salvar arquivo")
                if not path:
                    return
            if path:
                self._file_path = path
            with open(self._file_path, "w", encoding="utf-8") as f:
                f.write(self.get_text())
            self._dirty = False
            logger.info(f"[PlainCodeEditor] arquivo salvo: {self._file_path}")
        except Exception as e:
            logger.error(f"[PlainCodeEditor] save_file erro: {e}")
            QMessageBox.critical(self, "Erro", f"Falha ao salvar arquivo:\n{e}")

    def zoom_in(self):
        self.zoomIn(1)

    def zoom_out(self):
        self.zoomOut(1)

    def zoom_reset(self):
        self.setFont(QFont("Cascadia Code", 11))

class QsciCodeEditor(QPlainTextEdit):
    def __init__(self, language="python", parent=None):
        super().__init__(parent)
        raise RuntimeError("Implementação QScintilla adiada para simplificar. Use PlainCodeEditor ou ative depois.")

class CodeEditor(QWidget):
    def __init__(self, use_qsci=False, language="python", parent=None):
        super().__init__(parent)
        self._language = language
        self._use_qsci = use_qsci and HAS_QSCI
        self._dirty = False
        if self._use_qsci:
            logger.info("[CodeEditor] QScintilla ativado")
            self.impl = PlainCodeEditor(language, self)
        else:
            self.impl = PlainCodeEditor(language, self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.addWidget(self.impl)
        self.impl.textChanged.connect(self._on_dirty)

    def widget(self):
        return self.impl

    def _on_dirty(self):
        self._dirty = True

    def set_text(self, text: str):
        self.impl.set_text(text)

    def get_text(self) -> str:
        return self.impl.get_text()

    def set_language(self, lang: str):
        self.impl.set_language(lang)

    def open_file(self, path: str = None):
        self.impl.open_file(path)

    def save_file(self, path: str = None):
        self.impl.save_file(path)

    def is_dirty(self) -> bool:
        return getattr(self.impl, "_dirty", False)
