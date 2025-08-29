import logging
import os
import time

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QListWidget, QListWidgetItem, QToolButton,
    QAbstractItemView, QMessageBox, QMenu, QApplication, QMainWindow
)
import qtawesome as qta

from presentation.editor.tabs import EditorTabWidget
from presentation.editor.theming import ThemeManager
from presentation.editor.window_frame import RoundedFramelessWindow
from utils.utilities import COLOR_VARS

logger = logging.getLogger("FilePanel")


class FilePanel(QWidget):
    """Componente para exibir e gerenciar arquivos anexados."""
    def __init__(self, session, chat_id):
        super().__init__()
        self.session = session
        self.chat_id = chat_id
        self.file_list = QListWidget()
        self.setAcceptDrops(True)

        self._create_ui()
        self.load_files()
        self.update_toggle_btn()

        self.file_window = QMainWindow()
        self.theme_mgr = ThemeManager(self.file_window)
        self.theme_mgr.apply_dark()
        self._viewer = EditorTabWidget(self.file_window)
        self._viewer.on_change_theme.connect(self._on_theme_changed)
        self.file_window.setCentralWidget(self._viewer)
        self.frame = RoundedFramelessWindow(self.file_window, title="Code Editor Futurista", radius=14)

        self.file_list.itemDoubleClicked.connect(self._on_item_double_clicked)

        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.on_file_context_menu)
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.installEventFilter(self)

    def _on_theme_changed(self, theme_name: str):
        try:
            top = self.frame
            if hasattr(self, "theme_mgr"):
                self.theme_mgr.toggle()
            if hasattr(top, "set_theme"):
                top.set_theme(theme_name)
            if hasattr(self._viewer, "set_theme"):
                self._viewer.set_theme(theme_name)
        except Exception as e:
            logger.warning(f"[FilePanel] _on_theme_changed erro: {e}")

    def _create_button(self, icon_name: str, tooltip: str, callback) -> QToolButton:
        """Cria um QToolButton com ícone, tooltip e callback fornecidos."""
        btn = QToolButton()
        btn.setIcon(qta.icon(icon_name, color=COLOR_VARS['accent']))
        btn.setToolTip(tooltip)
        btn.clicked.connect(callback)
        return btn

    def _create_ui(self) -> None:
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel("Arquivos anexados:"))
        header.addStretch()

        self.toggle_btn = self._create_button(
            'fa5s.toggle-on', 'Desativar todos do prompt', self.on_toggle_from_prompts
        )
        header.addWidget(self.toggle_btn)

        self.remove_btn = self._create_button(
            'fa5s.trash', 'Excluir', self.on_remove_file
        )
        header.addWidget(self.remove_btn)

        layout.addLayout(header)
        layout.addWidget(self.file_list)

    def load_files(self) -> None:
        """Carrega itens da sessão e seus estados para a lista."""
        try:
            self.file_list.clear()
            for path in self.session.get_files(self.chat_id):
                try:
                    state = self.session.get_file_active(self.chat_id, path)
                except AttributeError:
                    state = True
                item = QListWidgetItem(
                    qta.icon('fa5s.file', color=COLOR_VARS['accent']),
                    os.path.basename(path)
                )
                item.setToolTip(path)
                item.setData(Qt.UserRole, state)
                self._apply_item_visual(item, state)
                self.file_list.addItem(item)
            self.update_toggle_btn()
        except Exception as e:
            logger.error(f"[FilePanel] falha ao carregar arquivos: {e}", exc_info=True)

    def _add_file_item(self, path: str, state: bool = True) -> None:
        """Insere um item na lista e salva estado na sessão."""
        for index in range(self.file_list.count()):
            if self.file_list.item(index).toolTip() == path:
                return
        item = QListWidgetItem(
            qta.icon('fa5s.file', color=COLOR_VARS['accent']),
            os.path.basename(path)
        )
        item.setToolTip(path)
        item.setData(Qt.UserRole, state)
        self._apply_item_visual(item, state)
        self.file_list.addItem(item)
        try:
            self.session.set_file_active(self.chat_id, path, state)
        except AttributeError:
            pass


    def on_attach_file(self, path: str) -> None:
        if path in self.session.get_files(self.chat_id):
            QMessageBox.warning(self, "Arquivo duplicado", f"O arquivo {path} já está anexado.")
            return
        self.session.add_file(self.chat_id, path)
        self._add_file_item(path)

    def on_attach_directory(self, directory: str) -> None:
        if directory in self.session.get_files(self.chat_id):
            QMessageBox.warning(self, "Diretório duplicado", f"O diretório {directory} já está anexado.")
            return
        self.session.add_file(self.chat_id, directory)
        self._add_file_item(directory)

    def apply_item_state(self, item: QListWidgetItem, state: bool) -> None:
        """Inverte e salva estado do item."""
        item.setData(Qt.UserRole, state)
        self._apply_item_visual(item, state)
        path = item.toolTip()
        try:
            self.session.set_file_active(self.chat_id, path, state)
        except AttributeError:
            pass

    def _apply_item_visual(self, item: QListWidgetItem, state: bool) -> None:
        color_key = 'accent' if state else 'disabled'
        item.setIcon(qta.icon('fa5s.file', color=COLOR_VARS[color_key]))
        item.setForeground(QBrush(QColor(COLOR_VARS['text'])))

    def on_remove_file(self) -> None:
        try:
            item = self.file_list.currentItem()
            if item:
                path = item.toolTip()
                self.file_list.takeItem(self.file_list.currentRow())
                self.session.remove_file(self.chat_id, path)
        except Exception as e:
            logger.error(f"[FilePanel] erro em on_remove_file: {e}", exc_info=True)

    def remove_selected_files(self) -> None:
        """Remove todos os itens selecionados da lista e da sessão."""
        selected = self.file_list.selectedItems()
        if not selected:
            return
        confirm = QMessageBox.question(
            self, "Remover arquivos",
            f"Remover {len(selected)} arquivo(s) selecionado(s)?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return
        for item in selected:
            path = item.toolTip()
            try:
                self.session.remove_file(self.chat_id, path)
            except Exception as e:
                logger.error(f"[FilePanel] falha ao remover sessão para {path}: {e}", exc_info=True)
            row = self.file_list.row(item)
            self.file_list.takeItem(row)

    def _toggle_item(self, item: QListWidgetItem) -> None:
        """Inverte o estado do item e atualiza o toggle_btn."""
        new_state = not item.data(Qt.UserRole)
        self.apply_item_state(item, new_state)
        self.update_toggle_btn()

    def on_toggle_from_prompts(self) -> None:
        """Alterna todos os itens e delega a atualização do botão a update_toggle_btn."""
        try:
            is_deactivated = self.toggle_btn.toolTip() == 'Ativar todos no prompt'
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                self.apply_item_state(item, is_deactivated)
            self.update_toggle_btn()
        except Exception as e:
            logger.error(f"[FilePanel] erro ao alternar todos itens: {e}", exc_info=True)

    def update_toggle_btn(self) -> None:
        """Ajusta o ícone e tooltip do toggle_btn conforme o estado de todos os itens."""
        items = [self.file_list.item(i) for i in range(self.file_list.count())]
        if not items:
            return
        all_active = all(item.data(Qt.UserRole) for item in items)
        all_disabled = all(not item.data(Qt.UserRole) for item in items)
        if all_disabled:
            icon, tip = 'fa5s.toggle-off', 'Ativar todos no prompt'
        elif all_active:
            icon, tip = 'fa5s.toggle-on', 'Desativar todos do prompt'
        else:
            icon, tip = 'fa5s.toggle-on', 'Ativar todos no prompt'
        self.toggle_btn.setIcon(qta.icon(icon, color=COLOR_VARS['accent']))
        self.toggle_btn.setToolTip(tip)

    def build_context_menu(self, items_to_toggle: list) -> QMenu:
        """Cria e retorna o menu de contexto para os itens especificados."""
        current_states = [item.data(Qt.UserRole) for item in items_to_toggle]
        activate = not all(current_states)
        menu = QMenu()
        open_action = menu.addAction('Abrir no Explorer')
        toggle_text = 'Ativar no prompt' if activate else 'Desativar do prompt'
        toggle_action = menu.addAction(toggle_text)
        menu._open_action = open_action
        menu._toggle_action = toggle_action
        menu._activate = activate
        return menu

    def on_file_context_menu(self, pos) -> None:
        """Exibe menu de contexto operando sobre seleção."""
        try:
            clicked_item = self.file_list.itemAt(pos)
            if not clicked_item:
                return
            selected = self.file_list.selectedItems()
            if clicked_item in selected and len(selected) > 1:
                items_to_toggle = selected
            else:
                items_to_toggle = [clicked_item]
            menu = self.build_context_menu(items_to_toggle)
            action = menu.exec_(self.file_list.viewport().mapToGlobal(pos))
            if action == menu._open_action:
                os.startfile(clicked_item.toolTip())
            elif action == menu._toggle_action:
                for item in items_to_toggle:
                    self._toggle_item(item)
        except Exception as e:
            logger.error(f"[FilePanel] erro no menu de contexto: {e}", exc_info=True)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        path = item.toolTip()
        if self.frame.isVisible():
            self.frame.activateWindow()
            self.frame.raise_()
        else:
            self.frame.show()
        self._viewer.new_tab(path, os.path.basename(path))
        # self._viewer.load_file(path)
        # self._viewer.show()

    def eventFilter(self, source, event) -> bool:
        if source is self.file_list and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Delete:
                self.remove_selected_files()
                return True
        return super().eventFilter(source, event)

    def dragEnterEvent(self, event) -> None:
        """Aceita o evento de arraste se houver URLs (arquivos)."""
        mime = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()
            logger.info("[FilePanel] dragEnterEvent: URLs detectadas")
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        """Permite mover enquanto arrasta sobre o widget."""
        mime = event.mimeData()
        if mime.hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        """Anexa arquivos (ou pasta recursiva) sem duplicar caminhos."""
        try:
            existing = {
                os.path.normcase(os.path.abspath(p))
                for p in self.session.get_files(self.chat_id)
            }

            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if not path:
                    continue

                abs_path = os.path.abspath(path)
                norm_path = os.path.normcase(abs_path)

                if os.path.isdir(abs_path):
                    for root, _, files in os.walk(abs_path):
                        for fname in files:
                            file_abs = os.path.abspath(os.path.join(root, fname))
                            norm_fp = os.path.normcase(file_abs)
                            if norm_fp not in existing:
                                self.session.add_file(self.chat_id, file_abs)
                                self._add_file_item(file_abs)
                                existing.add(norm_fp)
                                logger.info(f"[FilePanel] anexado: {file_abs}")
                            else:
                                logger.info(f"[FilePanel] ignorado (duplicado): {file_abs}")
                else:
                    if norm_path not in existing:
                        self.session.add_file(self.chat_id, abs_path)
                        self._add_file_item(abs_path)
                        existing.add(norm_path)
                        logger.info(f"[FilePanel] anexado: {abs_path}")
                    else:
                        logger.info(f"[FilePanel] ignorado (duplicado): {abs_path}")

            event.acceptProposedAction()
        except Exception as e:
            logger.error(f"[FilePanel] erro no dropEvent: {e}", exc_info=True)
            QMessageBox.warning(self, "Erro", "Falha ao anexar arquivos arrastados.")