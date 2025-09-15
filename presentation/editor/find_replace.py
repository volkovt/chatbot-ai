import logging
from qtpy.QtCore import Qt, QRegularExpression, QEvent
from qtpy.QtGui import QTextCursor, QTextDocument, QKeySequence
from qtpy.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel, QCheckBox, QShortcut

import qtawesome as qta

logger = logging.getLogger("FuturisticEditor")

class FindReplaceBar(QWidget):
    def __init__(self, host_editor, parent=None):
        super().__init__(parent)
        self._scope = None
        self.editor = host_editor
        self.setAutoFillBackground(True)
        self.setObjectName("FindReplaceBar")
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find")
        self.find_edit.setMinimumSize(100, 0)
        self.rep_edit = QLineEdit()
        self.rep_edit.setPlaceholderText("Replace")
        self.rep_edit.setMinimumSize(100, 0)
        self.case_cb = QCheckBox("Aa")
        self.case_cb.setToolTip("Case Sensitive")
        self.regex_checkbox = QCheckBox(".*")
        self.regex_checkbox.setToolTip("Use Regular Expressions")
        self.word_checkbox = QCheckBox("W")
        self.word_checkbox.setToolTip("Match Whole Words")
        self.btn_prev = QPushButton("")
        self.btn_prev.setIcon(qta.icon("fa5s.arrow-up", color="orange"))
        self.btn_next = QPushButton("")
        self.btn_next.setIcon(qta.icon("fa5s.arrow-down", color="orange"))
        self.btn_rep = QPushButton("Replace")
        self.btn_rep.setMinimumSize(80, 0)
        self.btn_all = QPushButton("Replace All")
        self.btn_all.setMinimumSize(80, 0)
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(6)
        h.addWidget(QLabel("Find:"))
        h.addWidget(self.find_edit, 1)
        h.addWidget(QLabel("Replace:"))
        h.addWidget(self.rep_edit, 1)
        h.addWidget(self.case_cb)
        h.addWidget(self.regex_checkbox)
        h.addWidget(self.word_checkbox)
        h.addWidget(self.btn_prev)
        h.addWidget(self.btn_next)
        h.addWidget(self.btn_rep)
        h.addWidget(self.btn_all)
        self._wire()

    def _wire(self):
        try:
            self.find_edit.textChanged.connect(self._find_incremental)

            self.find_edit.installEventFilter(self)
            self.rep_edit.installEventFilter(self)

            self.btn_next.clicked.connect(self._find_next)
            self.btn_prev.clicked.connect(self._find_prev)

            self.btn_rep.clicked.connect(self._replace_one)
            self.btn_all.clicked.connect(self._replace_all)

            QShortcut(QKeySequence(Qt.Key_Return), self, member=self._find_next)
            QShortcut(QKeySequence(Qt.Key_Enter), self, member=self._find_next)
            QShortcut(QKeySequence("Escape"), self, member=self._hide_self)
        except Exception as e:
            logger.error(f"[FindReplaceBar] erro ao conectar sinais: {e}")

    def _current_editor(self):
        if self.editor is None:
            return None
        return self.editor

    def find_input(self):
        return self.find_edit

    def _find_next(self):
        """Botão Next."""
        try:
            return self._find(
                forward=True,
                use_regex=self.regex_checkbox.isChecked(),
                case_sensitive=self.case_cb.isChecked(),
                whole_word=self.word_checkbox.isChecked()
            )
        except Exception as e:
            logger.error(f"[FindReplaceBar] _find_next erro: {e}")
            return False

    def _find_prev(self):
        """Botão Prev."""
        try:
            return self._find(
                forward=False,
                use_regex=self.regex_checkbox.isChecked(),
                case_sensitive=self.case_cb.isChecked(),
                whole_word=self.word_checkbox.isChecked()
            )
        except Exception as e:
            logger.error(f"[FindReplaceBar] _find_prev erro: {e}")
            return False

    def _find_incremental(self):
        """Busca incremental do texto do campo, para frente, respeitando flags."""
        try:
            return self._find(
                forward=True,
                use_regex=self.regex_checkbox.isChecked(),
                case_sensitive=self.case_cb.isChecked(),
                whole_word=self.word_checkbox.isChecked()
            )
        except Exception as e:
            logger.error(f"[FindReplaceBar] _find_incremental erro: {e}")
            return False

    def _find(self, forward=True, use_regex=False, case_sensitive=False, whole_word=False):
        try:
            editor = self._current_editor()
            if editor is None:
                logger.info("[FindReplaceBar] _find: sem editor atual")
                return False

            pattern = self.find_input().text()
            if not pattern:
                self._clear_editor_selection()
                return False

            flags = QTextDocument.FindFlags()
            if not forward:
                flags |= QTextDocument.FindBackward
            if case_sensitive:
                flags |= QTextDocument.FindCaseSensitively
            if whole_word:
                flags |= QTextDocument.FindWholeWords

            # >>> NOVO: posiciona início da busca respeitando o escopo (se houver)
            start_cursor = editor.textCursor()
            scoped_start = self._scoped_start_cursor(forward)
            if scoped_start is not None:
                editor.setTextCursor(scoped_start)
            # <<< NOVO

            if not use_regex:
                found = editor.find(pattern, flags)

                # >>> NOVO: wrap apenas dentro do escopo
                if not found:
                    wrap_cursor = editor.textCursor()
                    if self._scope is not None:
                        s, e = self._scope
                        wrap_cursor.setPosition(s if forward else e)
                    else:
                        wrap_cursor.movePosition(QTextCursor.Start if forward else QTextCursor.End)
                    editor.setTextCursor(wrap_cursor)
                    found = editor.find(pattern, flags)
                # <<< NOVO

                logger.info(f"[FindReplaceBar] _find simples: found={found}")
                if found:
                    # >>> NOVO: invalida se o match sair do escopo
                    if self._scope is not None and not self._in_scope(editor.textCursor()):
                        editor.setTextCursor(start_cursor)
                        self._clear_editor_selection()
                        return False
                    # <<< NOVO
                    editor.centerCursor()
                else:
                    editor.setTextCursor(start_cursor)
                    self._clear_editor_selection()
                return found

            # --- bloco regex ---
            doc = editor.document()
            # usamos doc.find com um cursor explícito
            cstart = editor.textCursor()  # usado apenas para restore em falha

            try:
                regex = QRegularExpression(pattern)
                if whole_word and regex.isValid():
                    regex = QRegularExpression(f"\\b{pattern}\\b")
                if regex.isValid():
                    if not case_sensitive:
                        regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
                else:
                    raise ValueError(regex.errorString())

                # >>> NOVO: busca a partir do início escopado
                search_from = self._scoped_start_cursor(forward)
                if search_from is None:
                    search_from = editor.textCursor()

                found_cursor = doc.find(regex, search_from, flags)

                if found_cursor.isNull():
                    # Wrap dentro do escopo
                    wrap_from = editor.textCursor()
                    if self._scope is not None:
                        s, e = self._scope
                        wrap_from.setPosition(s if forward else e)
                    else:
                        wrap_from.movePosition(QTextCursor.Start if forward else QTextCursor.End)
                    found_cursor = doc.find(regex, wrap_from, flags)

                found = not found_cursor.isNull()
                logger.info(f"[FindReplaceBar] _find regex: found={found}")

                if found and self._scope is not None and not self._in_scope(found_cursor):
                    found = False

                if found:
                    editor.setTextCursor(found_cursor)
                    editor.centerCursor()
                else:
                    editor.setTextCursor(cstart)
                    self._clear_editor_selection()
                return found

            except Exception as e:
                logger.error(f"[FindReplaceBar] _find regex erro: {e}")
                editor.setTextCursor(start_cursor)
                return False
        except Exception as e:
            logger.error(f"[FindReplaceBar] _find erro: {e}")
            return False

    def _replace_one(self):
        try:
            editor = self._current_editor()
            if editor is None:
                logger.warn("[FindReplaceBar] _replace_one: sem editor")
                return
            cur = editor.textCursor()
            if self._scope is not None:
                s, e = self._scope
                if not (cur.hasSelection() and cur.selectionStart() >= s and cur.selectionEnd() <= e):
                    self._find_next()
                    return
            if cur.hasSelection():
                cur.insertText(self.rep_edit.text())
            self._find_next()
        except Exception as e:
            logger.error(f"[FindReplaceBar] _replace_one erro: {e}")

    def _replace_all(self):
        try:
            editor = self._current_editor()
            if editor is None:
                logger.warn("[FindReplaceBar] _replace_all: sem editor")
                return 0

            use_regex = self.regex_checkbox.isChecked()
            case_sensitive = self.case_cb.isChecked()
            whole_word = self.word_checkbox.isChecked()
            replacement = self.rep_edit.text()

            # Sem escopo → mantém lógica existente
            if self._scope is None:
                count = 0
                cur = editor.textCursor()
                cur.movePosition(QTextCursor.Start)
                editor.setTextCursor(cur)
                while self._find(forward=True, use_regex=use_regex, case_sensitive=case_sensitive,
                                 whole_word=whole_word):
                    editor.textCursor().insertText(replacement)
                    count += 1
                logger.info(f"[FindReplaceBar] _replace_all total={count}")
                return count

            s, e = self._scope
            doc = editor.document()
            matches = []

            flags = QTextDocument.FindFlags()
            if case_sensitive:
                flags |= QTextDocument.FindCaseSensitively
            if whole_word:
                flags |= QTextDocument.FindWholeWords

            c = editor.textCursor()
            c.setPosition(s)

            if not use_regex:
                while True:
                    found = doc.find(self.find_edit.text(), c, flags)
                    if found.isNull() or found.selectionStart() >= e:
                        break
                    if found.selectionEnd() <= e:
                        matches.append((found.selectionStart(), found.selectionEnd()))
                    c.setPosition(found.selectionEnd())
            else:
                regex = QRegularExpression(self.find_edit.text())
                if whole_word and regex.isValid():
                    regex = QRegularExpression(f"\\b{self.find_edit.text()}\\b")
                if regex.isValid() and not case_sensitive:
                    regex.setPatternOptions(QRegularExpression.CaseInsensitiveOption)
                while True:
                    found = doc.find(regex, c, flags)
                    if found.isNull() or found.selectionStart() >= e:
                        break
                    if found.selectionEnd() <= e:
                        matches.append((found.selectionStart(), found.selectionEnd()))
                    c.setPosition(found.selectionEnd())

            for start, end in reversed(matches):
                cur = editor.textCursor()
                cur.setPosition(start)
                cur.setPosition(end, QTextCursor.KeepAnchor)
                cur.insertText(replacement)

            logger.info(f"[FindReplaceBar] _replace_all (escopo) total={len(matches)}")
            return len(matches)

        except Exception as e:
            logger.error(f"[FindReplaceBar] _replace_all erro: {e}")
            return 0

    def _clear_editor_selection(self):
        try:
            editor = self._current_editor()
            if editor is None:
                logger.warn("[FindReplaceBar] _clear_editor_selection: sem editor")
                return
            cur = editor.textCursor()
            if cur.hasSelection():
                cur.clearSelection()
                editor.setTextCursor(cur)
                if hasattr(editor, "viewport"):
                    editor.viewport().update()
            logger.info("[FindReplaceBar] seleção limpa (sem matches)")
        except Exception as e:
            logger.error(f"[FindReplaceBar] _clear_editor_selection erro: {e}")

    def attach_to_editor(self, editor=None):
        try:
            if editor is not None:
                self.editor = editor
            ed = self._current_editor()
            if ed is None:
                logger.warn("[FindReplaceBar] attach_to_editor: sem editor")
                return

            self.setParent(ed.viewport())
            self.setVisible(False)
            self.raise_()

            vp = ed.viewport()
            vp.removeEventFilter(self)
            vp.installEventFilter(self)

            if hasattr(ed, "verticalScrollBar"):
                sb = ed.verticalScrollBar()
                try:
                    try:
                        sb.valueChanged.disconnect(self._sync_geometry)
                    except TypeError:
                        pass
                    sb.valueChanged.connect(self._sync_geometry)
                except Exception as e:
                    logger.warn(f"[FindReplaceBar] attach_to_editor: valueChanged connect: {e}")

            try:
                ed.cursorPositionChanged.disconnect(self._sync_geometry)
            except:
                pass
            ed.cursorPositionChanged.connect(self._sync_geometry)

            try:
                ed.updateRequest.disconnect()
            except:
                pass
            try:
                ed.updateRequest.connect(lambda *_: self._sync_geometry())
            except Exception as e:
                logger.warn(f"[FindReplaceBar] attach_to_editor: updateRequest connect: {e}")

            logger.info("[FindReplaceBar] ancorado ao viewport do editor")
        except Exception as e:
            logger.error(f"[FindReplaceBar] attach_to_editor erro: {e}")

    def _apply_viewport_margins(self, enable: bool):
        try:
            ed = self._current_editor()
            if ed is None:
                return

            h = self.height() if self.isVisible() else self.sizeHint().height()
            top = h - 50 if enable else 0
            if top < 0:
                top = 0
            if hasattr(ed, "setViewportMargins"):
                ed.setViewportMargins(0, top, 0, 0)
        except Exception as e:
            logger.error(f"[FindReplaceBar] _apply_viewport_margins erro: {e}")

    def _sync_geometry(self):
        """Mantém a barra colada no topo e com largura do viewport, ajustando para o scroll."""
        try:
            ed = self._current_editor()
            if ed is None or self.parent() is None:
                return
            vp = ed.viewport()
            w = vp.width()
            self.setFixedWidth(w)

            self.move(0, 0)
            self.raise_()
        except Exception as e:
            logger.error(f"[FindReplaceBar] _sync_geometry erro: {e}")

    def set_scope(self, start: int, end: int):
        """Define o intervalo [start, end) como escopo da busca."""
        if start is None or end is None or end <= start:
            self._scope = None
            return
        self._scope = (min(start, end), max(start, end))
        logger.info(f"[FindReplaceBar] escopo definido: {self._scope}")

    def clear_scope(self):
        """Remove escopo de busca (volta a buscar no documento inteiro)."""
        self._scope = None
        logger.info("[FindReplaceBar] escopo limpo")

    def _current_scope_from_editor(self):
        """Se o editor tiver seleção 'manual', usa como escopo; do contrário, limpa."""
        ed = self._current_editor()
        if ed is None:
            self.clear_scope()
            return
        cur = ed.textCursor()
        if cur and cur.hasSelection():
            self.set_scope(cur.selectionStart(), cur.selectionEnd())
        else:
            self.clear_scope()

    def _in_scope(self, cursor: 'QTextCursor') -> bool:
        """Confere se o cursor encontrado está contido no escopo ativo (se houver)."""
        if self._scope is None or cursor is None or cursor.isNull():
            return True
        s, e = self._scope
        return cursor.selectionStart() >= s and cursor.selectionEnd() <= e

    def _scoped_start_cursor(self, forward: bool):
        """Retorna um QTextCursor posicionado no início (ou fim) do escopo,
        ou no cursor atual se estiver dentro do escopo."""
        ed = self._current_editor()
        if ed is None:
            return None
        cur = ed.textCursor()
        if self._scope is None:
            return cur

        s, e = self._scope
        pos = cur.position()
        if pos < s or pos > e:
            pos = s if forward else e
        c = ed.textCursor()
        c.setPosition(pos)
        return c

    def show(self):
        try:
            ed = self._current_editor()
            if ed is None:
                logger.warn("[FindReplaceBar] show: sem editor")
                return
            if self.parent() is not ed.viewport():
                self.attach_to_editor(ed)

            self._current_scope_from_editor()
            super().show()
            self._apply_viewport_margins(enable=True)
            self._sync_geometry()
            self.raise_()
            self.find_edit.setFocus()
        except Exception as e:
            logger.error(f"[FindReplaceBar] show erro: {e}")

    def hide(self):
        """Oculta a barra e restaura a margem do viewport."""
        try:
            self._apply_viewport_margins(enable=False)
            super().hide()
            ed = self._current_editor()
            if ed and hasattr(ed, "setFocus"):
                ed.setFocus()
        except Exception as e:
            logger.error(f"[FindReplaceBar] hide erro: {e}")

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
            if self.isVisible():
                self._apply_viewport_margins(enable=True)
                self._sync_geometry()
        except Exception as e:
            logger.error(f"[FindReplaceBar] resizeEvent erro: {e}")

    def wheelEvent(self, event):
        try:
            ed = self._current_editor()
            if not ed or not hasattr(ed, "verticalScrollBar"):
                return
            sb = ed.verticalScrollBar()
            dy = event.pixelDelta().y()
            if dy == 0:
                dy = event.angleDelta().y() / 120.0 * sb.singleStep()
            sb.setValue(sb.value() - int(dy))
            event.accept()
        except Exception as e:
            logger.error(f"[FindReplaceBar] wheelEvent erro: {e}")

    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self._hide_self()
                    return True

                if obj is self.find_edit and event.key() in (Qt.Key_Return, Qt.Key_Enter):
                    if event.modifiers() & Qt.ShiftModifier:
                        self._find_prev()
                    else:
                        self._find_next()
                    return True

            ed = self._current_editor()
            if ed and obj is ed.viewport():
                if event.type() in (QEvent.Resize, QEvent.Wheel):
                    self._sync_geometry()

            return super().eventFilter(obj, event)
        except Exception as e:
            logger.error(f"[FindReplaceBar] eventFilter erro: {e}")
            return False

    def _hide_self(self):
        try:
            self.hide()
            if hasattr(self.editor, "setFocus"):
                self.editor.setFocus()
            logger.info("[FindReplaceBar] oculto via ESC; foco devolvido ao editor")
        except Exception as e:
            logger.error(f"[FindReplaceBar] _hide_self erro: {e}")
