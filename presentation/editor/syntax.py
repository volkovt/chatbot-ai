import logging

from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from qtpy.QtGui import QColor, QTextCharFormat
from qtpy.QtGui import QSyntaxHighlighter

logger = logging.getLogger("FuturisticEditor")

LANG_EXT = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "java": "java",
    "html": "html",
    "htm": "html",
    "json": "json",
    "md": "markdown",
    "markdown": "markdown"
}

LEXER_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sql": "sql",
    ".xml": "xml",
}

def detect_language(file_path: str, fallback: str = "text") -> str:
    try:
        ext = file_path.split(".")[-1].lower()
        if ext in LANG_EXT:
            return LANG_EXT[ext]
        return fallback
    except Exception as e:
        logger.error(f"[syntax.detect_language] erro: {e}")
        return fallback

class PygmentsHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, lang_name="python", style_name="monokai"):
        super().__init__(parent)
        self._lang = lang_name
        self._style = style_name
        try:
            self._lexer = get_lexer_by_name(lang_name)
            self._style_cls = get_style_by_name(style_name)
            self._formats = {}
            for token, style in self._style_cls.styles.items():
                fmt = QTextCharFormat()
                if style:
                    parts = style.split()
                    for part in parts:
                        if part.startswith("bg:"):
                            fmt.setBackground(QColor("#" + part[3:]))
                        elif part.startswith("#"):
                            fmt.setForeground(QColor(part))
                        elif part == "bold":
                            fmt.setFontWeight(600)
                        elif part == "italic":
                            fmt.setFontItalic(True)
                        elif part == "underline":
                            fmt.setFontUnderline(True)
                self._formats[token] = fmt
        except Exception as e:
            logger.error(f"[PygmentsHighlighter] erro ao iniciar: {e}")

    def set_language(self, lang_name: str):
        try:
            self._lang = lang_name
            self._lexer = get_lexer_by_name(lang_name)
            self.rehighlight()
        except Exception as e:
            logger.error(f"[PygmentsHighlighter] set_language erro: {e}")

    def highlightBlock(self, text):
        try:
            for token, value in lex(text, self._lexer):
                length = len(value)
                if length:
                    fmt = self._formats.get(token, QTextCharFormat())
                    idx = 0
                    while idx < len(text):
                        pos = text.find(value, idx)
                        if pos == -1:
                            break
                        self.setFormat(pos, length, fmt)
                        idx = pos + length
        except Exception as e:
            logger.error(f"[PygmentsHighlighter] highlightBlock erro: {e}")
