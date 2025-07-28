import json
import logging
import os

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTextEdit, QMenu, QFileDialog,
    QLabel, QToolButton, QAction, QMessageBox, QSizePolicy, QPushButton,
    QSplitter
)
from PyQt5.QtCore import Qt, QEvent
import qtawesome as qta

from core.workers.ai_worker import AIWorker
from presentation.advanced_selection import AdvancedSelectionDialog
from presentation.custom_web_engine_view import CustomWebEngineView
from presentation.file_view import FilePanel
from presentation.loading_bar import FuturisticLoadingBar
from presentation.loading_button import LoadingButton
from presentation.toggle_splitter import ToggleSplitter
from utils.utilities import COLOR_VARS, get_base_path

logger = logging.getLogger("ChatTab")


class ChatTab(QWidget):
    """Abas de chat com histórico, entrada de texto, botões e anexos."""

    def __init__(self, chat_id: str, session_service) -> None:
        super().__init__()
        self.chat_id = chat_id
        self.session = session_service

        # estados de menus auxiliares
        self.worker = None
        self.kb_source_menu = None
        self.agent_menu = None
        self.conversation_menu = None

        # inicializa UI
        self._create_widgets()
        self._create_layout()
        self._connect_signals()

    def _create_widgets(self) -> None:
        """Inicializa todos os widgets usados."""
        # Web view para o histórico
        self.history = CustomWebEngineView()
        self.history.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._load_html()
        self.history.loadFinished.connect(self._load_history)

        # Campo de entrada de texto
        self.input = QTextEdit()
        self.input.setObjectName("PromptInput")
        self.input.setPlaceholderText("Digite seu prompt aqui...")
        self.input.setTabChangesFocus(True)
        self.input.setMaximumHeight(120)
        self.input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.input.installEventFilter(self)

        # Painel de arquivos
        self.file_panel = FilePanel(self.session, self.chat_id)

        # Barra de carregamento futurista
        self.loading = FuturisticLoadingBar()

        # Botão de enviar
        self.send_btn = self._make_button(
            icon_name="fa5s.paper-plane",
            tooltip="Enviar",
            handler=self.on_send
        )

        # Configurações dos botões do header
        self._header_buttons = [
            ("fa5s.plus",       self.on_add,          "Adicionar"),
            ("fa5s.trash",      self.on_delete,       "Excluir"),
            ("fa5s.sync",       self.on_refresh,      "Atualizar"),
            ("fa5s.sun",        self.on_toggle_theme, "Tema")
        ]

        # Botões adicionais no input
        self._input_buttons = [
            ("fa5s.robot", self.show_stackspot_menu, "Stackspot"),
            ("fa5s.cog",   self._show_config_menu,   "Configurações")
        ]

    def _create_layout(self) -> None:
        """Monta o layout principal, dividindo áreas com ToggleSplitter."""
        splitter = ToggleSplitter(Qt.Horizontal)

        # Widget esquerdo (chat)
        left = QWidget()
        vleft = QVBoxLayout(left)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("Digibot"))
        header.addStretch()
        for icon, handler, tip in self._header_buttons:
            header.addWidget(self._make_button(icon, tip, handler))
        vleft.addLayout(header)

        # Histórico e loading
        vleft.addWidget(self.history)
        vleft.addWidget(self.loading)

        # Área de input
        bottom = QHBoxLayout()
        bottom.addWidget(self.input)
        bottom.addWidget(self.send_btn)
        for icon, handler, tip in self._input_buttons:
            bottom.addWidget(self._make_button(icon, tip, handler))
        vleft.addLayout(bottom)

        splitter.addWidget(left)
        splitter.addWidget(self.file_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        # Layout final
        main = QVBoxLayout(self)
        main.addWidget(splitter)

    def _connect_signals(self) -> None:
        """Conecta sinais adicionais do CustomWebEngineView."""
        self.history.save_file_signal.connect(
            lambda filename: logger.info(f"[ChatTab] sinal save_file: {filename}")
        )
        self.history.load_finished_signal.connect(
            lambda: logger.info("[ChatTab] WebView carregado")
        )

    def _make_button(self, icon_name: str, tooltip: str, handler) -> LoadingButton:
        """Helper para criar LoadingButton com ícone do qtawesome."""
        btn = LoadingButton(
            text="",
            tooltip=tooltip,
            parent=self,
            icon=qta.icon(icon_name, color=COLOR_VARS["accent"]),
            spinner_size=20,
            spinner_thickness=3,
            colors=("#FF4081", "#7C4DFF")
        )
        if handler:
            btn.clicked.connect(handler)
        return btn

    def _load_html(self) -> None:
        """Carrega o HTML do chat view de forma assíncrona."""
        try:
            base = get_base_path()
            path = os.path.join(base, "resources", "chat", "chat_view.html")
            logger.info(f"[ChatTab] carregando HTML: {path}")
            self.history.loadHtmlAsync(path)
        except Exception as e:
            logger.error("[ChatTab] erro ao carregar HTML: %s", e, exc_info=True)

    def _load_history(self) -> None:
        """Injeta o histórico salvo na sessão dentro do WebView."""
        try:
            for msg in self.session.load_history(self.chat_id):
                if msg.startswith("Você: "):
                    self._append_message(msg[len("Você: "):], True)
                elif msg.startswith("AI: "):
                    self._append_message(msg[len("AI: "):], False)
                else:
                    self._append_message(msg, False)
        except Exception as e:
            logger.error("[ChatTab] erro ao carregar histórico: %s", e, exc_info=True)
            QMessageBox.critical(self, "Erro", "Não foi possível carregar o histórico.")

    def _append_message(self, text: str, is_user: bool) -> None:
        """Injeta uma mensagem no WebView via JavaScript."""
        try:
            code = f'addMessage({json.dumps(text)}, {str(is_user).lower()}, []);'
            self.history.page().runJavaScript(code)
        except Exception as e:
            logger.error("[ChatTab] erro ao injetar mensagem: %s", e, exc_info=True)

    def get_active_files(self) -> list[str]:
        """Retorna lista de paths dos arquivos marcados como ativos."""
        try:
            files = []
            for i in range(self.file_panel.file_list.count()):
                item = self.file_panel.file_list.item(i)
                if item.data(Qt.UserRole):
                    files.append(item.toolTip())
            return files
        except Exception as e:
            logger.error("[ChatTab] erro em get_active_files: %s", e, exc_info=True)
            return []

    def _show_config_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("Anexar arquivos...", self.on_attach_files)
        menu.exec_(self.send_btn.mapToGlobal(self.send_btn.rect().bottomRight()))

    def show_stackspot_menu(self) -> None:
        menu = QMenu(self)
        kb = QAction("Base de conhecimento", self)
        kb.triggered.connect(self.on_kb_source_action)
        ag = QAction("Agente", self)
        ag.triggered.connect(self.on_agent_action)
        cv = QAction("Conversação", self)
        cv.triggered.connect(self.on_conversation_action)
        menu.addActions([kb, ag, cv])
        menu.exec_(self.send_btn.mapToGlobal(self.send_btn.rect().bottomRight()))

    def on_attach_files(self) -> None:
        try:
            paths, _ = QFileDialog.getOpenFileNames(self, "Selecionar arquivos")
            if not paths:
                return
            for p in paths:
                self.session.add_file(self.chat_id, p)
                self._append_message(f"[Arquivo anexado] {os.path.basename(p)}", False)
            self.file_panel.load_files()
        except Exception as e:
            logger.error("[ChatTab] erro ao anexar arquivos: %s", e, exc_info=True)
            QMessageBox.warning(self, "Erro", "Falha ao anexar arquivos.")

    def on_send(self) -> None:
        """Envia o prompt ao AIWorker e injeta no WebView."""
        text = self.input.toPlainText().strip()
        if not text:
            return

        self.send_btn.setLoading(True)
        try:
            # salvar e exibir usuário
            self.session.save_message(self.chat_id, f"Você: {text}")
            self._append_message(text, True)

            # preparar IA
            files = self.get_active_files()
            self.loading.start()
            self.worker = AIWorker(text, files)
            self.worker.finished.connect(self.on_response)
            self.worker.error.connect(self.on_error)
            self.worker.start()

            # limpar input
            self.input.clear()

        except Exception as e:
            logger.error("[ChatTab] erro em on_send: %s", e, exc_info=True)
            QMessageBox.critical(self, "Erro", "Falha ao enviar mensagem.")
            self.send_btn.setLoading(False)

    def on_response(self, text: str) -> None:
        """Recebe resposta da IA e injeta no WebView."""
        try:
            self.loading.stop()
            self.send_btn.setLoading(False)
            self.session.save_message(self.chat_id, f"AI: {text}")
            self._append_message(text, False)

        except Exception as e:
            logger.error("[ChatTab] erro em on_response: %s", e, exc_info=True)
            QMessageBox.critical(self, "Erro", "Falha ao processar resposta.")
        finally:
            self.send_btn.setEnabled(True)

    def on_error(self, exc: Exception) -> None:
        """Tratamento de erro do AIWorker."""
        logger.error("[ChatTab] erro na IA: %s", exc, exc_info=True)
        QMessageBox.critical(self, "Erro", "Erro na comunicação com IA.")
        self._append_message("Erro ao obter resposta da IA", False)
        self.send_btn.setEnabled(True)

    def eventFilter(self, source, event) -> bool:
        """Captura Enter no QTextEdit para enviar."""
        if source is self.input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and event.modifiers() == Qt.NoModifier:
                self.on_send()
                return True
        return super().eventFilter(source, event)

    def on_kb_source_action(self) -> None:
        """Menu de seleção de fontes de conhecimento."""
        if self.kb_source_menu:
            try:
                self.kb_source_menu.close()
                self.kb_source_menu.deleteLater()
            except: pass

        lists_data = [
            [{"name": n, "description": d} for n, d in [
                ("Maçã","Uma fruta vermelha e doce"),("Banana","Fruta amarela rica em potássio"),
                ("Laranja","Suco cítrico refrescante"),("Uva","Pequena fruta roxa ou verde"),
                ("Manga","Fruta tropical suculenta"),("Abacaxi","Fruta com casca espinhosa"),
                ("Morango","Fruta vermelha com sementes"),("Pera","Fruta doce e suculenta"),
                ("Kiwi","Fruta pequena e peluda"),("Melancia","Fruta grande e refrescante")
            ]],
            [{"name": n, "description": d} for n, d in [
                ("Cachorro","Amigo leal do homem"),("Gato","Animal doméstico independente"),
                ("Papagaio","Ave que imita sons")
            ]],
            [{"name": n, "description": d} for n, d in [
                ("Carro","Veículo motorizado"),("Bicicleta","Veículo de duas rodas"),
                ("Avião","Veículo aéreo")
            ]]
        ]
        modes = [AdvancedSelectionDialog.SelectionMode.MULTI_SELECTION]*3
        titles = ["Pessoal","Compartilhada","Comunidade"]
        self.kb_source_menu = AdvancedSelectionDialog(lists_data, modes, titles)
        self.kb_source_menu.setWindowTitle("Seleção de Fontes de Conhecimento")
        self.kb_source_menu.actionSelected.connect(
            lambda idx, action, item: logger.info(f"KB action: {action} em {item} na lista {idx}")
        )

        # botões de cabeçalho extra
        h = QHBoxLayout()
        for icon, tip, cb in [
            ("fa5s.plus","Criar", lambda: QMessageBox.information(self,"Criar Fonte","Não implementado")),
            ("fa5s.trash","Excluir",lambda: QMessageBox.information(self,"Excluir Fonte","Não implementado")),
            ("fa5s.sync","Atualizar",lambda: QMessageBox.information(self,"Atualizar Fonte","Não implementado"))
        ]:
            btn = QPushButton("")
            btn.setIcon(qta.icon(icon, color=COLOR_VARS["accent"]))
            btn.setToolTip(tip)
            btn.clicked.connect(cb)
            h.addWidget(btn)
        self.kb_source_menu.add_header_widget(h)
        self.kb_source_menu.show()

    def on_agent_action(self) -> None:
        """Menu de seleção de agente."""
        if self.agent_menu:
            try:
                self.agent_menu.close()
                self.agent_menu.deleteLater()
            except: pass

        lists_data = [
            [{"name":"Stackspot AI","description":"Agente de IA padrão"},
             {"name":"Agente Pessoal","description":"Agente pessoal"}],
            # mesmos dados de frutas/pets como exemplo
            [{"name":n,"description":d} for n,d in [
                ("Maçã","..."),("Banana","..."),("Laranja","..."),("Uva","..."),
                ("Manga","..."),("Abacaxi","..."),("Morango","..."),
                ("Pera","..."),("Kiwi","..."),("Melancia","...")
            ]],
            [{"name":"Cachorro","description":"..."},
             {"name":"Gato","description":"..."},{"name":"Papagaio","description":"..."}],
            [{"name":"Carro","description":"..."},{"name":"Bicicleta","description":"..."},{"name":"Avião","description":"..."}]
        ]
        modes = [AdvancedSelectionDialog.SelectionMode.SINGLE_GLOBAL_SELECTION]
        titles = ["Padrão","Pessoal","Compartilhada","Comunidade"]
        self.agent_menu = AdvancedSelectionDialog(lists_data, modes, titles)
        self.agent_menu.setWindowTitle("Seleção de Agentes")
        self.agent_menu.actionSelected.connect(
            lambda idx, action, item: logger.info(f"Agent action: {action} em {item} na lista {idx}")
        )

        h = QHBoxLayout()
        for icon, tip, cb in [
            ("fa5s.plus","Criar", lambda: QMessageBox.information(self,"Criar Agente","Não implementado")),
            ("fa5s.trash","Excluir",lambda: QMessageBox.information(self,"Excluir Agente","Não implementado")),
            ("fa5s.sync","Atualizar",lambda: QMessageBox.information(self,"Atualizar Agente","Não implementado"))
        ]:
            btn = QPushButton("")
            btn.setIcon(qta.icon(icon, color=COLOR_VARS["accent"]))
            btn.setToolTip(tip)
            btn.clicked.connect(cb)
            h.addWidget(btn)
        self.agent_menu.add_header_widget(h)
        self.agent_menu.show()

    def on_conversation_action(self) -> None:
        """Menu de seleção de conversação."""
        if self.conversation_menu:
            try:
                self.conversation_menu.close()
                self.conversation_menu.deleteLater()
            except: pass

        lists_data = [[
            {"name":"Conversa A","description":"Exemplo de conversa"},
            {"name":"Conversa B","description":"Outro exemplo"}
        ]]
        modes = [AdvancedSelectionDialog.SelectionMode.SINGLE_GLOBAL_SELECTION]
        titles = ["Conversas"]
        self.conversation_menu = AdvancedSelectionDialog(
            lists_data, modes, titles,
            selection_actions=[AdvancedSelectionDialog.SelectionAction.VISUALIZE]
        )
        self.conversation_menu.setWindowTitle("Seleção de Conversas")
        self.conversation_menu.actionSelected.connect(
            lambda idx, action, item: logger.info(f"Conv action: {action} em {item} na lista {idx}")
        )

        # botão de confirmação no footer
        f = QHBoxLayout()
        btn = QPushButton("Confirmar")
        btn.setIcon(qta.icon("fa5s.check", color=COLOR_VARS["accent"]))
        btn.setToolTip("Confirmar seleção")
        btn.clicked.connect(lambda: QMessageBox.information(self,"Confirmar","Não implementado"))
        f.addWidget(btn)
        self.conversation_menu.add_footer_widget(f)
        self.conversation_menu.show()

    # stubs que permanecem para implementação futura
    def on_add(self):             raise NotImplementedError
    def on_delete(self):          raise NotImplementedError
    def on_refresh(self):         raise NotImplementedError
    def on_toggle_theme(self):    raise NotImplementedError
