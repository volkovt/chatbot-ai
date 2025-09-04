import ctypes

from qtpy.QtCore import QTimer, QLibraryInfo
from qtpy.QtWidgets import QApplication

from presentation.futuristic_window import FuturisticWindow
from presentation.main_window import MainWindow
from utils.utilities import get_style_sheet

import resources_rc

import logging, os, sys
from qtpy.QtCore import QLibraryInfo

logger = logging.getLogger(__name__)

SERVER_NAME = "ChatbotAIReady"

def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def setup_qtwebengine_env():
    try:
        if not getattr(sys, "frozen", False):
            logger.info("[QtWebEngine] ambiente dev: não vou setar variáveis.")
            return
        prefix   = QLibraryInfo.location(QLibraryInfo.PrefixPath) or ""
        data_dir = QLibraryInfo.location(QLibraryInfo.DataPath) or ""
        tr_dir   = QLibraryInfo.location(QLibraryInfo.TranslationsPath) or ""
        bin_dir  = QLibraryInfo.location(QLibraryInfo.LibraryExecutablesPath) or ""

        res_dir  = os.path.join(data_dir, "resources")
        loc_dir  = os.path.join(tr_dir, "qtwebengine_locales")
        proc_exe = os.path.join(bin_dir, "QtWebEngineProcess.exe")

        def _export_if_exists(var, path):
            if path and os.path.exists(path):
                if os.environ.get(var) in (None, "", " "):
                    os.environ[var] = path
                    logger.info(f"[QtWebEngine] {var}={path}")
            else:
                logger.warn(f"[QtWebEngine] ignorando {var}, caminho inexistente: {path}")

        _export_if_exists("QTWEBENGINE_RESOURCES_PATH", res_dir)
        _export_if_exists("QTWEBENGINE_LOCALES_PATH",   loc_dir)
        if os.name == "nt":
            _export_if_exists("QTWEBENGINEPROCESS_PATH", proc_exe)

    except Exception as e:
        logger.error(f"[QtWebEngine] erro configurando ambiente: {e}")


def _signal_win_event(name: str):
    try:
        k32 = ctypes.windll.kernel32
        SYNCHRONIZE = 0x00100000
        EVENT_MODIFY_STATE = 0x0002
        handle = k32.OpenEventW(SYNCHRONIZE | EVENT_MODIFY_STATE, False, name)
        if not handle:
            handle = k32.CreateEventW(None, False, False, name)  # auto-reset, inicialmente não-sinalizado
        if handle:
            k32.SetEvent(handle)
            k32.CloseHandle(handle)
            logger.info(f"[Bootstrap] Evento sinalizado: {name}")
        else:
            logger.warn(f"[Bootstrap] Falha ao abrir/criar evento: {name}")
    except Exception as e:
        logger.error(f"[Bootstrap] Erro sinalizando {name}: {e}")

def notify_launcher_ready():
    for ev in (r"Local\CHATBOT_AI_READY", r"Global\CHATBOT_AI_READY", r"CHATBOT_AI_READY"):
        _signal_win_event(ev)

def signal_ready_when_ui_is_stable():
    for ms in (200, 1500, 5000):
        QTimer.singleShot(ms, notify_launcher_ready)

if __name__ == "__main__":
    import infra.logging_service as logsvc
    logsvc.configure_logging()

    try:
        setup_qtwebengine_env()

        logger.info("[Bootstrap] iniciando QApplication...")
        app = QApplication(sys.argv)
        logger.info("[Bootstrap] QApplication iniciada.")
        core = MainWindow()
        logger.info("[Bootstrap] MainWindow criada.")

        shell = FuturisticWindow(core)
        try:
            logger.info("[Bootstrap] aplicando stylesheet...")
            shell.setStyleSheet(get_style_sheet())
            logger.info("[Bootstrap] stylesheet aplicado.")
        except Exception as e:
            logger.info(f"[Bootstrap] stylesheet não aplicado: {e}")

        shell.setWindowTitle(core.windowTitle() or "ChatbotAI — Neon 2500")

        shell.resize(1100, 700)
        logger.info("[Bootstrap] mostrando janela principal...")
        shell.show()
        logger.info("[Bootstrap] janela principal mostrada.")
        try:
            signal_ready_when_ui_is_stable()
            shell.raise_()
            shell.activateWindow()
        except Exception as e:
            logger.info(f"[Bootstrap] raise_/activateWindow falhou: {e}")
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"[Bootstrap] erro ao iniciar: {e}")

