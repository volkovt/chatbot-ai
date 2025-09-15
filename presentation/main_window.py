import logging

from qtpy.QtCore import QEvent, Qt
from qtpy.QtWidgets import (
    QMainWindow, QTabWidget, QMenu, QInputDialog, QMessageBox, QToolButton
)

from core.service.session_service import SessionService
from presentation.chat_tab import ChatTab
from presentation.log_viewer import LogViewerDialog
from utils.utilities import COLOR_VARS
import qtawesome as qta

logger = logging.getLogger("MainWindow")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.log_viewer = None
        try:
            # self.setWindowTitle("Chatbot AI")
            # self.setStyleSheet(get_style_sheet())
            # self.resize(800, 600)
            self.tabs = QTabWidget()
            self.tabs.setTabsClosable(True)
            self.tabs.tabCloseRequested.connect(self.close_tab)
            self.tabs.tabBar().installEventFilter(self)

            self.logs_button = QToolButton()
            self.logs_button.setIcon(qta.icon('fa5s.stream', color=COLOR_VARS['accent']))
            self.logs_button.setToolTip('Ver Logs')
            self.logs_button.clicked.connect(self.show_logs)
            self.tabs.setCornerWidget(self.logs_button, Qt.TopRightCorner)

            self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
            self.tabs.tabBar().customContextMenuRequested.connect(self.on_tab_context_menu)
            self.setCentralWidget(self.tabs)

            self.session_service = SessionService()
            chats = self.session_service.list_chats()

            if not chats:
                self.new_chat()
            else:
                for idx, chat_id in enumerate(chats, start=1):
                    saved = self.session_service.get_chat_title(chat_id)
                    title = saved if saved else f"Chat {idx}"
                    logger.info(f"[MainWindow] restaurando sessão {chat_id} como '{title}'")
                    tab = ChatTab(chat_id, self.session_service)
                    self.tabs.addTab(tab, title)
        except Exception as e:
            logger.error(f"[MainWindow] erro ao inicializar UI: {e}", exc_info=True)

    def show_logs(self):
        """Abre o diálogo de visualização de logs com abas."""
        try:
            self.log_viewer = LogViewerDialog()
            self.log_viewer.show()
        except Exception as e:
            logger.error(f"[MainWindow] erro ao abrir Visualizador de Logs: {e}", exc_info=True)

    def close_tab(self, index):
        """Fecha a aba no índice especificado e remove sessão."""
        try:
            widget = self.tabs.widget(index)
            chat_id = getattr(widget, 'chat_id', None)
            if chat_id:
                try:
                    self.session_service.delete_chat(chat_id)
                except Exception as se:
                    logger.error(f"[MainWindow] erro ao deletar sessão {chat_id}: {se}", exc_info=True)

            self.tabs.removeTab(index)
            widget.deleteLater()
            if self.tabs.count() == 0:
                self.new_chat()
        except Exception as e:
            logger.error(f"[MainWindow] erro ao fechar aba {index}: {e}", exc_info=True)

    def new_chat(self):
        """Cria nova aba de chat com número incremental e registra na sessão."""
        try:
            chat_id = self.session_service.create_chat()
            count = self.tabs.count() + 1
            title = f"Chat {count}"
            self.session_service.rename_chat(chat_id, title)

            tab = ChatTab(chat_id, self.session_service)
            self.tabs.addTab(tab, title)
            self.tabs.setCurrentWidget(tab)
        except Exception as e:
            logger.error(f"[MainWindow] erro ao criar novo chat: {e}", exc_info=True)

    def rename_tab(self, index):
        old_name = self.tabs.tabText(index)
        new_name, ok = QInputDialog.getText(self, "Renomear Aba", "Novo nome:", text=old_name)
        if ok and new_name and new_name != old_name:
            for i in range(self.tabs.count()):
                if i != index and self.tabs.tabText(i) == new_name:
                    QMessageBox.warning(self, "Nome duplicado", f"O nome '{new_name}' já existe.")
                    return
            self.tabs.setTabText(index, new_name)
            widget = self.tabs.widget(index)
            chat_id = getattr(widget, 'chat_id', None)
            if chat_id:
                try:
                    self.session_service.rename_chat(chat_id, new_name)
                except Exception as se:
                    logger.error(f"[MainWindow] erro ao renomear sessão {chat_id}: {se}", exc_info=True)

    def on_tab_context_menu(self, pos):
        """Mostra menu de contexto para renomeação da aba."""
        try:
            bar = self.tabs.tabBar()
            index = bar.tabAt(pos)
            if index < 0:
                return
            menu = QMenu()
            rename_action = menu.addAction('Renomear aba')
            action = menu.exec_(bar.mapToGlobal(pos))
            if action == rename_action:
                self.rename_tab(index)
        except Exception as e:
            logger.error(f"[MainWindow] erro no menu de contexto da aba: {e}", exc_info=True)

    def eventFilter(self, source, event):
        if source == self.tabs.tabBar() and event.type() == QEvent.MouseButtonDblClick:
            self.new_chat()
            return True
        return super().eventFilter(source, event)
