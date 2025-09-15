# -*- coding: utf-8 -*-
"""
Launcher com splash + sincronização READY via QLocalServer.
Coloque este launcher.exe na mesma pasta do ChatbotAI.exe.
"""
import os, sys, subprocess, logging
from qtpy.QtWidgets import QApplication, QSplashScreen
from qtpy.QtCore import Qt, QTimer, QCoreApplication
from qtpy.QtGui import QPixmap, QMovie
from qtpy.QtNetwork import QLocalServer

from utils.utilities import get_base_path

# --- logging básico ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("Launcher")

SERVER_NAME = "ChatbotAIReady"
MAIN_EXE_NAME = "ChatbotAI.exe"

def base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class AnimatedSplash(QSplashScreen):
    def __init__(self, pixmap=None, movie_path=None):
        if movie_path:
            # Usar QMovie para GIF animado
            self.movie = QMovie(movie_path)
            pm = QPixmap(self.movie.currentPixmap())
            super().__init__(pm, Qt.WindowStaysOnTopHint | Qt.SplashScreen)
            self.movie.frameChanged.connect(self._on_frame_changed)
            self.movie.start()
        else:
            super().__init__(pixmap or QPixmap(), Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def _on_frame_changed(self):
        self.setPixmap(self.movie.currentPixmap())

def make_splash():
    """Procura splash no mesmo diretório: resources/loading.gif, depois resources/app.png."""
    logger.info("[Launcher] procurando splash...")
    b = get_base_path()
    logger.info(f"[Launcher] base_dir: {b}")
    gif_candidates = ["resources/loading.gif", "resources/loader.gif"]
    png_candidates = ["resources/app.png", "resources/splash.png"]
    for g in gif_candidates:
        p = os.path.join(b, g)
        if os.path.exists(p):
            s = AnimatedSplash(movie_path=p)
            s.show()
            logger.info(f"[Launcher] mostrando splash: {p}")
            return s
    for p in png_candidates:
        fp = os.path.join(b, p)
        if os.path.exists(fp):
            s = AnimatedSplash(pixmap=QPixmap(fp))
            s.show()
            logger.info(f"[Launcher] mostrando splash: {fp}")
            return s
    # fallback neutro
    logger.info("[Launcher] splash não encontrado, usando neutro.")
    s = QSplashScreen(QPixmap(1,1))
    s.setWindowFlag(Qt.FramelessWindowHint, True)
    s.setAttribute(Qt.WA_TranslucentBackground, True)
    s.show()
    return s

def launch_main():
    """Inicia o executável principal."""
    b = base_dir()
    exe_path = os.path.join(b, MAIN_EXE_NAME)
    if not os.path.exists(exe_path):
        raise FileNotFoundError(f"Arquivo principal não encontrado: {exe_path}")
    # Passa args do launcher -> main (exceto argv[0])
    args = [exe_path] + sys.argv[1:]
    logger.info(f"[Launcher] iniciando: {args}")
    # CREATE_NO_WINDOW evita console no spawn quando launcher for GUI
    creationflags = 0x08000000 if os.name == "nt" else 0
    try:
        subprocess.Popen(args, cwd=b, creationflags=creationflags)
    except Exception as e:
        logger.error(f"[Launcher] falha ao iniciar main: {e}")
        raise

def main():
    # Dica: não elevar privilégios nem mexer com registro aqui, para reduzir heurísticas de AV.
    app = QApplication(sys.argv)

    # Garantir nome único do servidor (remove resquício de instância anterior)
    try:
        QLocalServer.removeServer(SERVER_NAME)
    except Exception:
        pass

    server = QLocalServer()
    if not server.listen(SERVER_NAME):
        # se já estiver em uso, provavelmente a app já está subindo, encerra splash rápido
        logger.warning(f"[Launcher] QLocalServer.listen falhou em '{SERVER_NAME}', prosseguindo assim mesmo.")
    splash = make_splash()

    # Inicia o principal
    try:
        launch_main()
    except Exception:
        # encerra após alguns segundos para o usuário ver algo
        QTimer.singleShot(2500, QCoreApplication.quit)
        return app.exec_()

    # Fecha quando receber READY
    def on_new_conn():
        try:
            conn = server.nextPendingConnection()
            if conn and conn.waitForReadyRead(1000):
                data = bytes(conn.readAll()).decode(errors="ignore").strip().upper()
                logger.info(f"[Launcher] sinal recebido: {data}")
                if "READY" in data:
                    if splash:
                        splash.close()
                    QTimer.singleShot(100, QCoreApplication.quit)
        except Exception as e:
            logger.error(f"[Launcher] erro ready: {e}")

    if server.isListening():
        server.newConnection.connect(on_new_conn)

    QTimer.singleShot(30000, lambda: (splash and splash.close(), QCoreApplication.quit()))

    return app.exec_()

if __name__ == "__main__":
    import infra.logging_service as logsvc
    logsvc.configure_logging("logs_launcher")

    sys.exit(main())
