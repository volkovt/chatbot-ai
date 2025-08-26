import logging
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from presentation.futuristic_window import FuturisticWindow
from presentation.main_window import MainWindow
from utils.utilities import get_style_sheet

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import infra.logging_service as logsvc
    logsvc.configure_logging()

    try:
        app = QApplication(sys.argv)
        core = MainWindow()

        shell = FuturisticWindow(core)
        try:
            shell.setStyleSheet(get_style_sheet())
        except Exception as e:
            logger.warn(f"[Bootstrap] stylesheet não aplicado: {e}")

        shell.setWindowTitle(core.windowTitle() or "ChatbotAI — Neon 2500")

        shell.resize(1100, 700)
        shell.show()
        try:
            shell.raise_()
            shell.activateWindow()
        except Exception as e:
            logger.warning(f"[Bootstrap] raise_/activateWindow falhou: {e}")
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"[Bootstrap] erro ao iniciar: {e}")

