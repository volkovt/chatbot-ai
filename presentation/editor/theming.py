import logging
from PyQt5.QtWidgets import QApplication, QMainWindow

logger = logging.getLogger("ThemeManager")

DARK_QSS = """
/* Base */
QWidget { background-color: #0f1115; color: #e8e8e8; }
QToolBar { background: #12151c; border: none; padding: 4px; }
QTabWidget::pane { border: 1px solid #232838; border-radius: 10px; }
QTabBar::tab { background: #171b25; padding: 8px 14px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
QTabBar::tab:selected { background: #1f2431; }
QLineEdit, QPlainTextEdit { background: #0e1118; border: 1px solid #2b3246; border-radius: 8px; selection-background-color: #264f78; }
QScrollBar:vertical { width: 10px; background: transparent; }
QScrollBar::handle:vertical { background: #2a2f3e; border-radius: 5px; min-height: 30px; }
QPushButton { background: #1f2431; border: 1px solid #2b3246; border-radius: 8px; padding: 6px 10px; }
QPushButton:hover { background: #262c3a; }
"""

LIGHT_QSS = """
QWidget { background-color: #f7f7fb; color: #1d2330; }
QToolBar { background: #ffffff; border: none; padding: 4px; }
QTabWidget::pane { border: 1px solid #dadee8; border-radius: 10px; }
QTabBar::tab { background: #edf0f7; padding: 8px 14px; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; }
QTabBar::tab:selected { background: #ffffff; }
QLineEdit, QPlainTextEdit { background: #ffffff; border: 1px solid #ccd3e0; border-radius: 8px; selection-background-color: #a3d2ff; }
QScrollBar:vertical { width: 10px; background: transparent; }
QScrollBar::handle:vertical { background: #cfd6e4; border-radius: 5px; min-height: 30px; }
QPushButton { background: #ffffff; border: 1px solid #ccd3e0; border-radius: 8px; padding: 6px 10px; }
QPushButton:hover { background: #f1f4fa; }
"""

class ThemeManager:
    def __init__(self, app: QMainWindow):
        self.app = app
        self._current = "dark"

    def _reset_stylesheet(self):
        self.app.setStyleSheet("")

    def apply_dark(self):
        try:
            self._reset_stylesheet()
            self.app.setStyleSheet(DARK_QSS)
            self._current = "dark"
        except Exception as e:
            logger.error(f"[ThemeManager] erro ao aplicar tema dark: {e}")

    def apply_light(self):
        try:
            self._reset_stylesheet()
            self.app.setStyleSheet(LIGHT_QSS)
            self._current = "light"
        except Exception as e:
            logger.error(f"[ThemeManager] erro ao aplicar tema light: {e}")

    def current(self) -> str:
        return self._current

    def toggle(self):
        if self._current == "dark":
            self.apply_light()
        else:
            self.apply_dark()