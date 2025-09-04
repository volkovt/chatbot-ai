import logging

from qtpy.QtCore import Signal, Qt, QObject, QThread
from qtpy.QtWebChannel import QWebChannel
from qtpy.QtWidgets import QMenu, QAction

try:
    from qtpy.QtWebEngineWidgets import QWebEngineView  # força o empacotamento
except Exception:
    logging.getLogger(__name__).warning("QtWebEngine não disponível.")
    pass

class HTMLLoaderWorker(QObject):
    finished = Signal(str)

    def __init__(self, html_path):
        super().__init__()
        self.html_path = html_path

    def run(self):
        try:
            with open(self.html_path, "r", encoding="utf-8") as file:
                html_content = file.read()
        except Exception as e:
            html_content = f"<html><body><h1>Erro ao carregar HTML: {e}</h1></body></html>"
        self.finished.emit(html_content)

class CustomWebEngineView(QWebEngineView):
    save_file_signal = Signal(str)
    load_finished_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loader_worker = None
        self.loader_thread = None
        self.current_theme = "dracula"
        self.is_loaded = False
        self.loadFinished.connect(self.on_load_finished)
        self.setAcceptDrops(False)

        self.channel = QWebChannel(self.page())
        self.page().setWebChannel(self.channel)

    def on_load_finished(self, success):
        self.is_loaded = success
        self.load_finished_signal.emit()

    def contextMenuEvent(self, event):
        """Substitui o menu de contexto padrão."""
        menu = QMenu(self)

        back_action = QAction("Back", self)
        back_action.triggered.connect(self.back)
        menu.addAction(back_action)

        forward_action = QAction("Forward", self)
        forward_action.triggered.connect(self.forward)
        menu.addAction(forward_action)

        reload_action = QAction("Reload", self)
        reload_action.triggered.connect(self.reload)
        menu.addAction(reload_action)

        save_page_action = QAction("Save page", self)
        save_page_action.triggered.connect(self.save_page)
        menu.addAction(save_page_action)

        view_source_action = QAction("View page source", self)
        view_source_action.triggered.connect(self.view_source)
        menu.addAction(view_source_action)

        menu.exec_(event.globalPos())

    def keyPressEvent(self, event):
        """Intercepta eventos de tecla."""
        if event.key() == Qt.Key_S and event.modifiers() & Qt.ControlModifier:
            self.save_file_signal.emit("saved_page.html")
        else:
            super().keyPressEvent(event)

    def save_page(self):
        """Salva a página atual (implementação básica)."""
        self.page().save("saved_page.html")

    def view_source(self):
        """Exibe o código-fonte da página atual."""
        def handle_source(html):
            print("Código-fonte da página:")
            print(html)

        self.page().toHtml(handle_source)

    def load_theme(self, mode="dracula"):
        """Carrega dinamicamente o tema no QWebEngineView."""
        css_file = f"resources/chat/chat_styles_{mode}.css"
        try:
            with open(css_file, "r", encoding="utf-8") as file:
                css_content = file.read()

            self.page().runJavaScript(f"""changeStyleSheet(`{css_content}`);""")
        except FileNotFoundError:
            print(f"Arquivo de estilo '{css_file}' não encontrado.")

    def changeTheme(self, mode="dracula"):
        """Alterna entre temas claro e escuro."""
        self.current_theme = mode
        self.load_theme(mode)

    def get_editor_content(self, callback):
        """Executa um script JavaScript para obter o conteúdo do editor."""
        script = "editor.getValue();"
        self.page().runJavaScript(script, callback)

    def is_page_loaded(self):
        return self.is_loaded

    def loadHtmlAsync(self, html_path):
        self.loader_thread = QThread()
        self.loader_worker = HTMLLoaderWorker(html_path)
        self.loader_worker.moveToThread(self.loader_thread)

        self.loader_worker.finished.connect(self.on_html_loaded)
        self.loader_thread.started.connect(self.loader_worker.run)
        self.loader_thread.start()

    def on_html_loaded(self, html_content):
        self.setHtml(html_content)
        self.loader_thread.quit()
        self.loader_thread.wait()
