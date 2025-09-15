import logging, os
import shutil

from qtpy.QtCore import Signal
from qtpy.QtWidgets import QWidget, QTabWidget, QVBoxLayout, QToolBar, QAction, QFileDialog, QMessageBox, QLabel, \
    QSplitter, QMenu
from qtpy.QtCore import Qt
import qtawesome as qta

from presentation.editor.editor_core import CodeEditor
from presentation.editor.minimap import MiniMapWidget
from presentation.editor.syntax import detect_language

logger = logging.getLogger("EditorTabWidget")

class EditorTabWidget(QWidget):
    on_change_theme = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._show_tab_context_menu)

        self.current_theme = "dark"

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8,8,8,8)
        lay.setSpacing(6)
        lay.addWidget(self.toolbar)
        lay.addWidget(self.tabs, 1)
        self._make_actions()
        self.set_theme(self.current_theme)

    def _make_actions(self):
        try:
            self.act_new = QAction(qta.icon("ph.file-plus", color="white"), "Novo", self)
            self.act_open = QAction(qta.icon("ph.folder-open", color="white"), "Abrir", self)
            self.act_save = QAction(qta.icon("ph.floppy-disk", color="white"), "Salvar", self)
            self.act_save_as = QAction(qta.icon("ph.floppy-disk-back", color="white"), "Salvar como", self)
            self.act_refresh = QAction(qta.icon("ph.arrow-clockwise", color="white"), "Atualizar todos", self)
            self.act_theme = QAction(qta.icon("ph.moon", color="white"), "Tema", self)
            self.toolbar.addAction(self.act_new)
            self.toolbar.addAction(self.act_open)
            self.toolbar.addAction(self.act_save)
            self.toolbar.addAction(self.act_save_as)
            self.toolbar.addAction(self.act_refresh)
            self.toolbar.addSeparator()
            self.toolbar.addAction(self.act_theme)
            self.act_new.triggered.connect(lambda: self.new_tab())
            self.act_open.triggered.connect(self.open_file)
            self.act_save.triggered.connect(lambda: self.save_file(as_new=False))
            self.act_save_as.triggered.connect(lambda: self.save_file(as_new=True))
            self.act_refresh.triggered.connect(lambda: [self._refresh_tab_file(i) for i in range(self.tabs.count())])
            self.act_theme.triggered.connect(self.toggle_theme_request)
        except Exception as e:
            logger.error(f"[EditorTabWidget] erro ao criar ações: {e}")

    def set_theme(self, theme_name: str):
        try:
            self.current_theme = theme_name

            icon_color = "orange" if theme_name == "dark" else "#ff0000"
            self.act_new.setIcon(qta.icon("ph.file-plus", color=icon_color))
            self.act_open.setIcon(qta.icon("ph.folder-open", color=icon_color))
            self.act_save.setIcon(qta.icon("ph.floppy-disk", color=icon_color))
            self.act_save_as.setIcon(qta.icon("ph.floppy-disk-back", color=icon_color))
            self.act_refresh.setIcon(qta.icon("ph.arrow-clockwise", color=icon_color))

            self.act_theme.setIcon(qta.icon("ph.moon" if theme_name == "dark" else "ph.sun", color=icon_color))
        except Exception as e:
            logger.warning(f"[EditorTabWidget] set_theme erro: {e}")

    def current_editor(self) -> CodeEditor:
        w = self.tabs.currentWidget()
        if not w:
            return None
        return w.findChild(CodeEditor)

    def new_tab(self, text="", title="Sem título"):
        try:
            container = QWidget()
            split = QSplitter()
            split.setOrientation(Qt.Horizontal)
            editor = CodeEditor(use_qsci=False, language="python")
            minimap = MiniMapWidget()
            minimap.bind(editor.widget())
            split.addWidget(editor)
            split.addWidget(minimap)
            split.setStretchFactor(0, 8)
            split.setStretchFactor(1, 2)
            lay = QVBoxLayout(container)
            lay.setContentsMargins(0,0,0,0)
            lay.addWidget(split, 1)
            idx = self.tabs.addTab(container, title)
            self.tabs.setCurrentIndex(idx)
            editor.set_text(text)
            editor.widget().textChanged.connect(lambda: self._mark_dirty(idx, True))
        except Exception as e:
            logger.error(f"[EditorTabWidget] new_tab erro: {e}")

    def _mark_dirty(self, idx, dirty=True):
        try:
            t = self.tabs.tabText(idx)
            if dirty and not t.endswith("*"):
                self.tabs.setTabText(idx, t + "*")
            if not dirty and t.endswith("*"):
                self.tabs.setTabText(idx, t[:-1])
        except Exception as e:
            logger.error(f"[EditorTabWidget] _mark_dirty erro: {e}")

    def open_file(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Abrir arquivo")
            if not path:
                return

            title = os.path.basename(path)
            self.new_tab("", title)

            ed = self.current_editor()
            if ed:
                ed.open_file(path)
                idx = self.tabs.currentIndex()
                self._mark_dirty(idx, False)
                self._set_tab_title_and_tooltip(idx, path)

            logger.info(f"[EditorTabWidget] arquivo aberto: {path}")
        except Exception as e:
            logger.error(f"[EditorTabWidget] open_file erro: {e}")
            QMessageBox.critical(self, "Erro", f"Falha ao abrir:\n{e}")

    def save_file(self, as_new=False):
        try:
            ed = self.current_editor()
            if not ed:
                return

            path = None
            if as_new:
                path, _ = QFileDialog.getSaveFileName(self, "Salvar como")
                if not path:
                    return

            ed.save_file(path)

            idx = self.tabs.currentIndex()
            real_path = getattr(ed.widget(), "_file_path", None)
            if real_path:
                title = os.path.basename(real_path)
                self.tabs.setTabText(idx, title)
                self._set_tab_title_and_tooltip(idx, real_path)

            self._mark_dirty(idx, False)
        except Exception as e:
            logger.error(f"[EditorTabWidget] save_file erro: {e}")
            QMessageBox.critical(self, "Erro", f"Falha ao salvar:\n{e}")

    def _close_tab(self, idx):
        try:
            self.tabs.removeTab(idx)
        except Exception as e:
            logger.error(f"[EditorTabWidget] _close_tab erro: {e}")

    def toggle_theme_request(self):
        try:
            new_theme = "light" if self.current_theme == "dark" else "dark"
            self.set_theme(new_theme)
            self.on_change_theme.emit(new_theme)
        except Exception as e:
            logger.warning(f"[EditorTabWidget] toggle_theme_request sem handler: {e}")

    def _set_tab_title_and_tooltip(self, idx: int, path: str, dirty: bool = None):
        try:
            if path:
                title = os.path.basename(path)
                tooltip = path
            else:
                title = "Sem título"
                tooltip = "Sem arquivo associado"

            if dirty is None:
                is_dirty = self.tabs.tabText(idx).endswith("*")
            else:
                is_dirty = dirty

            self.tabs.setTabText(idx, title + ("*" if is_dirty else ""))
            self.tabs.setTabToolTip(idx, tooltip)
            logger.info(
                f"[EditorTabWidget] título/tooltip atualizados: idx={idx}, title={title}, sujo={is_dirty}, tip={tooltip}")
        except Exception as e:
            logger.error(f"[EditorTabWidget] _set_tab_title_and_tooltip erro: {e}")

    def _show_tab_context_menu(self, pos):
        try:
            tabbar = self.tabs.tabBar()
            idx = tabbar.tabAt(pos)
            if idx < 0:
                return

            menu = QMenu(self)
            act_dup = menu.addAction("Duplicar arquivo")
            act_refresh = menu.addAction("Atualizar")

            action = menu.exec_(tabbar.mapToGlobal(pos))
            if action == act_dup:
                self._duplicate_tab_file(idx)
            elif action == act_refresh:
                self._refresh_tab_file(idx)
        except Exception as e:
            logger.error(f"[EditorTabWidget] _show_tab_context_menu erro: {e}")

    def _duplicate_tab_file(self, idx: int):
        try:
            container = self.tabs.widget(idx)
            if not container:
                return
            ed: CodeEditor = container.findChild(CodeEditor)
            if not ed:
                return

            src_path = getattr(ed.widget(), "_file_path", None)
            if not src_path or not os.path.isfile(src_path):
                QMessageBox.information(self, "Duplicar arquivo", "A aba não está associada a um arquivo salvo.")
                return

            base = os.path.basename(src_path)
            name, ext = os.path.splitext(base)
            suggested = os.path.normpath(os.path.join(os.path.dirname(src_path), f"{name} - cópia{ext}"))

            dst_path, _ = QFileDialog.getSaveFileName(self, "Salvar cópia como", suggested)
            is_saved = bool(dst_path)
            if not is_saved:
                dst_path = suggested

            if os.path.isfile(dst_path):
                shutil.copyfile(src_path, dst_path)

            self.new_tab("", os.path.basename(dst_path))
            new_ed = self.current_editor()
            if new_ed:
                if is_saved:
                    new_ed.open_file(dst_path)
                else:
                    with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
                        data = f.read()
                    new_ed.set_text(data)
                    new_ed.widget()._file_path = None
                    lang = detect_language(ext.lstrip("."))
                    new_ed.set_language(lang)

                new_idx = self.tabs.currentIndex()
                self._set_tab_title_and_tooltip(new_idx, dst_path if is_saved else None)
                self._mark_dirty(new_idx, not is_saved)
        except Exception as e:
            logger.error(f"[EditorTabWidget] _duplicate_tab_file erro: {e}")
            QMessageBox.critical(self, "Erro", f"Falha ao duplicar arquivo:\n{e}")

    def _refresh_tab_file(self, idx: int):
        try:
            container = self.tabs.widget(idx)
            if not container:
                return
            ed: CodeEditor = container.findChild(CodeEditor)
            if not ed:
                return

            t = self.tabs.tabText(idx)
            if t.endswith("*"):
                resp = QMessageBox.question(self, "Atualizar", "A aba possui alterações não salvas.\nDeseja salvar antes de atualizar?",
                                            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                if resp == QMessageBox.Yes:
                    self.tabs.setCurrentIndex(idx)
                    self.save_file(as_new=False)

            path = getattr(ed.widget(), "_file_path", None)
            if not path or not os.path.isfile(path):
                QMessageBox.information(self, "Atualizar", "A aba não está associada a um arquivo salvo.")
                return

            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = f.read()

            ed.set_text(data)
            self._mark_dirty(idx, False)
            self._set_tab_title_and_tooltip(idx, path)
            logger.info(f"[EditorTabWidget] arquivo recarregado (Atualizar): {path}")
        except Exception as e:
            logger.error(f"[EditorTabWidget] _refresh_tab_file erro: {e}")
            QMessageBox.critical(self, "Erro", f"Falha ao atualizar arquivo:\n{e}")

