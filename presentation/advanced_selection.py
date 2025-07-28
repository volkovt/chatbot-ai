import logging
from enum import Enum
from functools import partial

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QLineEdit, QListWidget, QListWidgetItem, QSplitter,
    QTextEdit, QMenu, QSizePolicy, QLabel,
    QCheckBox, QRadioButton, QButtonGroup, QMainWindow, QBoxLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject

from utils.utilities import get_style_sheet

logger = logging.getLogger("[AdvancedSelector]")

class AdvancedSelectionDialog(QDialog):
    """
        Diálogo genérico para seleção avançada com múltiplas listas.

        Parâmetros:
        - lists_data: lista de listas de dicionários com campos 'name' e 'description'.
        - selection_modes: lista de SelectionMode (NO_SELECTION, SINGLE_SELECTION,
          SINGLE_GLOBAL_SELECTION ou MULTI_SELECTION) para cada lista.
        - list_titles: lista de strings com títulos para cada lista.

        Behavior:
        - NO_SELECTION: itens sem controle, clicáveis para mostrar descrição.
        - SINGLE_SELECTION: rádios locais exclusivos por lista.
        - SINGLE_GLOBAL_SELECTION: rádios globais exclusivos entre todas as listas.
        - MULTI_SELECTION: checkboxes independentes, emite todos marcados.
    """
    class SelectionMode(Enum):
        NO_SELECTION = 0
        SINGLE_SELECTION = 1
        MULTI_SELECTION = 2
        SINGLE_GLOBAL_SELECTION = 3

    class SelectionAction(Enum):
        EDIT = 0
        VISUALIZE = 1
        DELETE = 2

    itemSelected = pyqtSignal(int, list)
    actionSelected = pyqtSignal(int, SelectionAction, object)

    def __init__(
        self,
        lists_data: list[list[dict]],
        selection_modes: list['AdvancedSelectionDialog.SelectionMode'] | None = None,
        list_titles: list[str] | None = None,
        selection_actions=None,
        name_key="name",
        description_key="description",
        parent=None
    ):
        super().__init__(parent)
        self.setStyleSheet(get_style_sheet())
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )

        self.name_key = name_key
        self.description_key = description_key

        self._orig_lists_data = [list(lst) for lst in lists_data]
        self.lists_data = lists_data

        try:
            if selection_modes and len(selection_modes) == len(lists_data):
                self.selection_modes = selection_modes
            else:
                if 1 <= len(selection_modes) < len(lists_data):
                    self.selection_modes = selection_modes + selection_modes[-1:] * (len(lists_data) - len(selection_modes))
                else:
                    self.selection_modes = [self.SelectionMode.NO_SELECTION] * len(lists_data)
            if list_titles and len(list_titles) == len(lists_data):
                self.list_titles = list_titles
            else:
                self.list_titles = [f"Lista {i+1}" for i in range(len(lists_data))]

            if any(mode == self.SelectionMode.SINGLE_GLOBAL_SELECTION for mode in self.selection_modes):
                self.global_btn_group = QButtonGroup(self)
                self.global_btn_group.setExclusive(True)

            if selection_actions:
                self.selection_actions = selection_actions
            else:
                self.selection_actions = list(self.SelectionAction)

            self._init_ui()
        except Exception as e:
            logger.error(f"[AdvancedSelector] erro ao inicializar modos de seleção: {e}", exc_info=True)

    def _init_ui(self):
        try:
            self.setWindowTitle("Seleção Avançada")
            self.setWindowModality(Qt.NonModal)

            main_layout = QVBoxLayout(self)
            main_layout.setAlignment(Qt.AlignTop)

            self.header_widget = QWidget(self)
            self.header_layout = QHBoxLayout(self.header_widget)
            main_layout.addWidget(self.header_widget)

            splitter = QSplitter(Qt.Horizontal, self)
            splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.list_widgets = []

            for idx, items in enumerate(self.lists_data):
                mode = self.selection_modes[idx]
                container = QWidget(self)
                container_layout = QVBoxLayout(container)

                title = QLabel(self.list_titles[idx], self)
                title.setStyleSheet("font-weight: bold; font-size: 14px;")
                container_layout.addWidget(title)

                search = QLineEdit(self)
                search.setPlaceholderText("Buscar...")
                search.textChanged.connect(lambda text, i=idx: self._filter_list(i, text))
                container_layout.addWidget(search)

                lw = QListWidget(self)
                lw.setContextMenuPolicy(Qt.CustomContextMenu)
                lw.customContextMenuRequested.connect(lambda pos, i=idx: self._show_context_menu(i, pos))

                btn_group = None
                if mode == self.SelectionMode.SINGLE_SELECTION:
                    btn_group = QButtonGroup(self)
                    btn_group.setExclusive(True)

                splitter.addWidget(container)
                container_layout.addWidget(lw)
                self.list_widgets.append((lw, items, btn_group))
                self._populate_list(idx)

            main_layout.addWidget(splitter)

            self.desc_viewer = QTextEdit(self)
            self.desc_viewer.setReadOnly(True)
            self.desc_viewer.setMinimumHeight(400)
            self.desc_viewer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.desc_viewer.setPlaceholderText("Selecione um item para ver a descrição...")
            main_layout.addWidget(self.desc_viewer)
            self.footer_widget = QWidget(self)
            self.footer_layout = QHBoxLayout(self.footer_widget)
            self.footer_layout.addStretch()
            main_layout.addWidget(self.footer_widget)

        except Exception as e:
            logger.error(f"[AdvancedSelector] erro ao inicializar UI: {e}", exc_info=True)

    def _populate_list(self, idx: int):
        """Popula a QListWidget com controles de seleção conforme mode."""
        try:
            lw, items, local_group = self.list_widgets[idx]
            mode = self.selection_modes[idx]
            lw.clear()
            for it in items:
                text = it.get(self.name_key, "")
                desc = it.get(self.description_key, "")
                item = QListWidgetItem()
                widget = QWidget()
                hl = QHBoxLayout(widget)
                hl.setObjectName("advanced_selection_item_layout")
                if mode == self.SelectionMode.MULTI_SELECTION:
                    ctrl = QCheckBox(text)
                    ctrl.stateChanged.connect(partial(self._handle_checkbox, idx, ctrl))
                elif mode == self.SelectionMode.SINGLE_SELECTION:
                    ctrl = QRadioButton(text)
                    local_group.addButton(ctrl)
                    ctrl.toggled.connect(partial(self._handle_radio, idx, ctrl))
                elif mode == self.SelectionMode.SINGLE_GLOBAL_SELECTION:
                    ctrl = QRadioButton(text)
                    self.global_btn_group.addButton(ctrl)
                    ctrl.setProperty('global_idx', idx)
                    ctrl.toggled.connect(partial(self._handle_global_radio, ctrl))
                else:
                    lbl = QLabel(text)
                    lbl.setProperty('description', desc)
                    lbl.mousePressEvent = lambda ev, c=lbl, i=idx: self._handle_click(i, c)
                    ctrl = lbl
                ctrl.setObjectName("advanced_selection_item_label")
                ctrl.setProperty('description', desc)
                ctrl.setProperty('name', text)
                ctrl.setProperty("item", it)
                hl.addWidget(ctrl)
                hl.addStretch()
                widget.setLayout(hl)
                item.setSizeHint(widget.sizeHint())
                lw.addItem(item)
                lw.setItemWidget(item, widget)
        except Exception as e:
            logger.error(f"[AdvancedSelector] erro ao popular lista {idx}: {e}", exc_info=True)

    def _filter_list(self, idx: int, text: str):
        """Refaz população com filtro por name e description."""
        try:
            lw, _, btn_group = self.list_widgets[idx]
            if not text:
                filtered = list(self._orig_lists_data[idx])
            else:
                txt = text.lower()
                original = self._orig_lists_data[idx]
                filtered = [it for it in original if txt in it['name'].lower() or txt in it['description'].lower()]
            self.lists_data[idx] = filtered
            self.list_widgets[idx] = (lw, filtered, btn_group)
            self._populate_list(idx)
        except Exception as e:
            logger.error(f"[AdvancedSelector] erro ao filtrar lista {idx}: {e}", exc_info=True)
            logger.error(f"[AdvancedSelector] erro filtrar lista {idx}: {e}", exc_info=True)


    def _handle_checkbox(self, idx: int, ctrl, state: int):
        try:
            if state == Qt.Checked:
                desc = ctrl.property('description')
                self.desc_viewer.setPlainText(desc)
                lw, _, _ = self.list_widgets[idx]
                selected = []
                for i in range(lw.count()):
                    w = lw.itemWidget(lw.item(i))
                    chk = w.findChild(QCheckBox)
                    if chk and chk.isChecked():
                        selected.append(chk.property('item'))
                self.itemSelected.emit(idx, selected)
        except Exception as e:
            logger.error(f"[AdvancedSelector] erro checkbox {idx}: {e}", exc_info=True)

    def _handle_radio(self, idx: int, ctrl, checked: bool):
        try:
            if checked:
                desc = ctrl.property('description')
                item = ctrl.property('item')
                self.desc_viewer.setPlainText(desc)
                self.itemSelected.emit(idx, [item])
        except Exception as e:
            logger.error(f"[AdvancedSelector] erro radio {idx}: {e}", exc_info=True)

    def _handle_global_radio(self, ctrl: QRadioButton, checked: bool):
        try:
            if checked:
                desc = ctrl.property('description')
                item = ctrl.property('item')
                idx = ctrl.property('global_idx')
                self.desc_viewer.setPlainText(desc)
                self.itemSelected.emit(idx, [item])
        except Exception as e:
            logger.error(f"[AdvancedSelector] erro global radio: {e}", exc_info=True)

    def _handle_click(self, idx: int, ctrl):
        try:
            desc = ctrl.property('description')
            self.desc_viewer.setPlainText(desc)
        except Exception as e:
            logger.error(f"[AdvancedSelector] erro click {idx}: {e}", exc_info=True)

    def _show_context_menu(self, idx, pos):
        lw, _, _ = self.list_widgets[idx]

        item = lw.itemAt(pos)
        if not item:
            return

        item_widget = lw.itemWidget(item)
        selected_item = None

        for child in item_widget.findChildren(QObject):
            if hasattr(child, 'property') and child.property('item'):
                selected_item = child.property('item')
                break

        if not selected_item:
            return

        menu = QMenu(lw)
        submenu = menu.addMenu("Ações")
        for action in self.selection_actions:
            if action == self.SelectionAction.VISUALIZE:
                submenu.addAction("Visualizar", lambda a=action, i=selected_item: self._actions_menu(idx, a, i))
            elif action == self.SelectionAction.EDIT:
                submenu.addAction("Editar", lambda a=action, i=selected_item: self._actions_menu(idx, a, i))
            elif action == self.SelectionAction.DELETE:
                submenu.addAction("Excluir", lambda a=action, i=selected_item: self._actions_menu(idx, a, i))
        menu.exec_(lw.viewport().mapToGlobal(pos))

    def _actions_menu(self, idx, action, item):
        self.actionSelected.emit(idx, action, item)

    def add_header_widget(self, widget: QWidget | QBoxLayout):
        """Permite adicionar widgets ao header."""
        if isinstance(widget, QBoxLayout):
            self.header_layout.addLayout(widget)
        else:
            self.header_layout.insertWidget(self.header_layout.count() - 1, widget)

    def add_footer_widget(self, widget: QWidget | QBoxLayout):
        """Permite adicionar widgets ao footer."""
        if isinstance(widget, QBoxLayout):
            self.footer_layout.addLayout(widget)
        else:
            self.footer_layout.insertWidget(self.header_layout.count() - 1, widget)
