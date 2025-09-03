import sys, logging
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout

from presentation.editor.tabs import EditorTabWidget
from presentation.editor.theming import ThemeManager
from presentation.editor.window_frame import RoundedFramelessWindow

class Root(QWidget):
    def __init__(self, theme_mgr: ThemeManager):
        super().__init__()
        self.theme_mgr = theme_mgr
        self.tabs = EditorTabWidget(parent=self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0,0,0,0)
        lay.addWidget(self.tabs)
        try:
            self.theme_mgr.themeChanged.connect(self._on_theme_changed)
        except Exception as e:
            logging.getLogger("FuturisticEditor").warning(f"[Root] themeChanged connect: {e}")

    def toggle_theme(self):
        try:
            self.theme_mgr.toggle()
            self.tabs.set_theme(self.theme_mgr.current())
        except Exception as e:
            logging.getLogger("FuturisticEditor").error(f"[Root] toggle_theme erro: {e}")

    def _on_theme_changed(self, theme_name: str):
        try:
            if hasattr(self.tabs, "set_theme"):
                self.tabs.set_theme(theme_name)
            top = self.window()
            if hasattr(top, "set_theme"):
                top.set_theme(theme_name)
        except Exception as e:
            logging.getLogger("FuturisticEditor").warning(f"[Root] _on_theme_changed erro: {e}")

def main():
    logger = logging.getLogger("FuturisticEditor")
    try:
        app = QApplication(sys.argv)
        theme = ThemeManager(app)
        theme.apply_dark()
        root = Root(theme)
        frame = RoundedFramelessWindow(root, title="Code Editor Futurista", radius=14)
        frame.show()
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"[main] erro fatal: {e}")

if __name__ == "__main__":
    main()
