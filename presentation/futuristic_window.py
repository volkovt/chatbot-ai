import sys, ctypes, logging, math
from PyQt5.QtCore import Qt, QRect, QPoint, QPropertyAnimation, QEasingCurve, QEvent, pyqtSignal, QRectF, QTimer
from PyQt5.QtGui import QPainter, QColor, QRegion, QPainterPath
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QVBoxLayout, QGraphicsDropShadowEffect, QLabel, \
    QHBoxLayout, QSizePolicy, QPushButton

from utils.utilities import get_style_sheet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("[FuturisticWindow]")

# ---- Aparência / UX ----
EDGE = 10        # área sensível para resize (maior = mais fácil)
RADIUS = 23      # aumentei o arredondamento para reforçar o look futurista

# Paleta Itaú
# Laranja principal, variação clara, azul profundo e fundo claro translúcido
try:
    PRIMARY = QColor("#FF6900")             # Laranja Itaú
    ACCENT  = QColor("#FF8C42")             # Laranja claro para hovers/acentos
    DEEP    = QColor("#001E62")             # Azul escuro Itaú
    BASE_BG = QColor(245, 245, 245, 235)    # Cinza claro translúcido de base
except Exception as e:
    logger.warn(f"[FuturisticWindow] falha ao definir paleta: {e}")
    PRIMARY = QColor(0xFF, 0x69, 0x00, 255)
    ACCENT  = QColor(255, 120, 40, 255)
    DEEP    = QColor(0, 30, 98, 255)
    BASE_BG = QColor(245, 245, 245, 230)

def lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
    try:
        r = int(c1.red()   + (c2.red()   - c1.red())   * t)
        g = int(c1.green() + (c2.green() - c1.green()) * t)
        b = int(c1.blue()  + (c2.blue()  - c1.blue())  * t)
        a = int(c1.alpha() + (c2.alpha() - c1.alpha()) * t)
        return QColor(r, g, b, a)
    except Exception as e:
        logger.warn(f"[FuturisticWindow] lerp_color erro: {e}")
        return c1

class TitleBar(QWidget):
    requestClose = pyqtSignal()
    requestMin = pyqtSignal()
    requestMaxToggle = pyqtSignal()
    requestDrag = pyqtSignal(QPoint)
    requestDoubleClick = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self.setObjectName("TitleBar")
            self._buttons = self._build_buttons()
            self._layout()
            self._press_pos = None
            self.setFixedHeight(48)
            self.setAttribute(Qt.WA_StyledBackground, True)
            self.setMouseTracking(True)
        except Exception as e:
            logger.error(f"[TitleBar] erro ao inicializar: {e}")

    def _layout(self):
        try:
            h = QHBoxLayout(self)
            h.setContentsMargins(16, 8, 12, 8)
            h.setSpacing(10)
            self._title = QLabel(self.window().windowTitle() or "Chatbot Futurístico")
            self._title.setObjectName("WindowTitle")
            self._title.setAttribute(Qt.WA_TranslucentBackground, True)
            self._title.setAutoFillBackground(False)

            spacer = QWidget()
            spacer.setAttribute(Qt.WA_TranslucentBackground, True)
            spacer.setAutoFillBackground(False)
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            h.addWidget(self._title)
            h.addWidget(spacer)
            for b in self._buttons:
                h.addWidget(b)
        except Exception as e:
            logger.error(f"[TitleBar] erro no layout: {e}")

    def _build_buttons(self):
        try:
            def mk(text, obj):
                btn = QPushButton(text)
                btn.setObjectName(obj)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setFixedSize(42, 30)
                btn.setProperty("isTitleButton", True)
                btn.setFocusPolicy(Qt.NoFocus)
                return btn

            bmin = mk("–", "BtnMin")
            bmax = mk("□", "BtnMax")
            bclose = mk("×", "BtnClose")

            bmin.clicked.connect(self.requestMin.emit)
            bmax.clicked.connect(self.requestMaxToggle.emit)
            bclose.clicked.connect(self.requestClose.emit)

            return [bmin, bmax, bclose]
        except Exception as e:
            logger.error(f"[TitleBar] erro em _build_buttons: {e}")
            return []

    def mousePressEvent(self, e):
        try:
            if e.button() == Qt.LeftButton:
                self._press_pos = e.globalPos()
                self.requestDrag.emit(self._press_pos)
        except Exception as e:
            logger.error(f"[TitleBar] mousePressEvent erro: {e}")

    def mouseMoveEvent(self, e):
        try:
            if self._press_pos:
                self.requestDrag.emit(e.globalPos())
        except Exception as e:
            logger.error(f"[TitleBar] mouseMoveEvent erro: {e}")

    def mouseReleaseEvent(self, e):
        self._press_pos = None

    def mouseDoubleClickEvent(self, e):
        try:
            if e.button() == Qt.LeftButton:
                self.requestDoubleClick.emit()
        except Exception as e:
            logger.error(f"[TitleBar] mouseDoubleClickEvent erro: {e}")


class FuturisticWindow(QMainWindow):
    def __init__(self, central_widget: QWidget = None, parent=None):
        super().__init__(parent)
        try:
            self._mica_enabled = False

            self.setObjectName("FuturisticWindow")
            self.setWindowTitle("ChatbotAI — Neon Itaú")
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WA_NoSystemBackground, True)
            self.setAutoFillBackground(False)

            self._titlebar = TitleBar(self)
            self._titlebar.requestClose.connect(self.close)
            self._titlebar.requestMin.connect(self.showMinimized)
            self._titlebar.requestMaxToggle.connect(self._toggle_max)
            self._titlebar.requestDrag.connect(self._drag_move)
            self._titlebar.requestDoubleClick.connect(self._toggle_max)

            container = QWidget()
            container.setObjectName("WindowContainer")
            container.setMouseTracking(True)

            v = QVBoxLayout(container)
            v.setContentsMargins(8, 8, 8, 8)
            v.setSpacing(0)
            v.addWidget(self._titlebar)
            if central_widget is None:
                cw = QWidget()
                cw.setObjectName("CentralPane")
                cw.setMouseTracking(True)
                v.addWidget(cw, 1)
            else:
                try:
                    central_widget.setMouseTracking(True)
                except Exception:
                    pass
                v.addWidget(central_widget, 1)
            self.setCentralWidget(container)

            self.setMouseTracking(True)
            QApplication.instance().installEventFilter(self)

            self._drag_offset = None
            self._resizing = False
            self._resize_edge = None
            self._edge_hover = None

            self._apply_shadow()
            self._try_enable_mica_or_acrylic()
            self._fade_in()
        except Exception as e:
            logger.error(f"[FuturisticWindow] erro ao inicializar: {e}")

    def eventFilter(self, obj, ev):
        try:
            if ev.type() == QEvent.MouseMove:
                wpos = self.mapFromGlobal(ev.globalPos())
                edge = self._hit_test(wpos)
                self._edge_hover = edge
                self._update_cursor(edge)
        except Exception as e:
            logger.warn(f"[FuturisticWindow] eventFilter erro: {e}")
        return super().eventFilter(obj, ev)

    def _apply_shadow(self):
        try:
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(34)
            effect.setOffset(0, 6)
            effect.setColor(QColor(0, 0, 0, 120))
            self.centralWidget().setGraphicsEffect(effect)
        except Exception as e:
            logger.warn(f"[FuturisticWindow] _apply_shadow erro: {e}")

    def _fade_in(self):
        try:
            self.setWindowOpacity(0.0)
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(240)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start()
            self._fade_anim = anim
        except Exception as e:
            logger.warn(f"[FuturisticWindow] _fade_in erro: {e}")

    def _toggle_max(self):
        try:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()
        except Exception as e:
            logger.error(f"[FuturisticWindow] _toggle_max erro: {e}")

    def _drag_move(self, global_pos: QPoint):
        try:
            if self.isMaximized():
                return
            if self._drag_offset is None:
                self._drag_offset = global_pos - self.frameGeometry().topLeft()
            self.move(global_pos - self._drag_offset)
        except Exception as e:
            logger.warn(f"[FuturisticWindow] _drag_move erro: {e}")

    def leaveEvent(self, e):
        try:
            self.unsetCursor()
            self._edge_hover = None
        except Exception:
            pass

    def paintEvent(self, e):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)

            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(self.rect(), Qt.transparent)

            rect = self.rect().adjusted(4, 4, -4, -4)
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), float(RADIUS), float(RADIUS))

            painter.setClipPath(path)

            painter.fillPath(path, BASE_BG)

            painter.setPen(Qt.NoPen)
            inner = rect.adjusted(1, 1, -1, -1)
            inner_path = QPainterPath()
            inner_path.addRoundedRect(QRectF(inner), float(RADIUS), float(RADIUS))
            soft_shadow = QColor(0, 0, 0, 55)
            painter.fillPath(inner_path, soft_shadow)

            glow = lerp_color(DEEP, PRIMARY, 0.40)
            glow.setAlpha(68)
            painter.fillPath(inner_path, glow)

            border_col = lerp_color(PRIMARY, ACCENT, 0.35)
            if self._edge_hover:
                border_col = lerp_color(border_col, ACCENT, 0.4)
            border_col.setAlpha(205)
            painter.setPen(border_col)
            painter.drawPath(path)

            # Máscara anti-serrilhado
            mrect = QRectF(rect)
            mrect.adjust(0.5, 0.5, -0.5, -0.5)
            mpath = QPainterPath()
            mpath.addRoundedRect(mrect, float(RADIUS), float(RADIUS))
            self.setMask(QRegion(mpath.toFillPolygon().toPolygon()))

        except Exception as e:
            logger.error(f"[FuturisticWindow] paintEvent erro: {e}")

    def mousePressEvent(self, e):
        try:
            if e.button() == Qt.LeftButton:
                edge = self._hit_test(e.pos())
                if edge:
                    self._resizing = True
                    self._resize_edge = edge
                    self._start_geo = self.geometry()
                    self._start_mouse = e.globalPos()
                else:
                    self._drag_offset = e.globalPos() - self.frameGeometry().topLeft()
        except Exception as e:
            logger.error(f"[FuturisticWindow] mousePressEvent erro: {e}")

    def mouseMoveEvent(self, e):
        try:
            if self._resizing and self._resize_edge:
                self._perform_resize(e.globalPos())
                return

            edge = self._hit_test(e.pos())
            self._edge_hover = edge
            self._update_cursor(edge)
        except Exception as e:
            logger.error(f"[FuturisticWindow] mouseMoveEvent erro: {e}")

    def mouseReleaseEvent(self, e):
        self._resizing = False
        self._resize_edge = None
        self._drag_offset = None

    def _hit_test(self, pos: QPoint):
        try:
            x = pos.x()
            y = pos.y()
            w = self.width()
            h = self.height()
            left = x <= EDGE
            right = x >= w - EDGE
            top = y <= EDGE
            bottom = y >= h - EDGE
            if top and left:
                return "TopLeft"
            if top and right:
                return "TopRight"
            if bottom and left:
                return "BottomLeft"
            if bottom and right:
                return "BottomRight"
            if top:
                return "Top"
            if bottom:
                return "Bottom"
            if left:
                return "Left"
            if right:
                return "Right"
            return None
        except Exception as e:
            logger.warn(f"[FuturisticWindow] _hit_test erro: {e}")
            return None

    def _update_cursor(self, edge):
        try:
            cursors = {
                "Top": Qt.SizeVerCursor,
                "Bottom": Qt.SizeVerCursor,
                "Left": Qt.SizeHorCursor,
                "Right": Qt.SizeHorCursor,
                "TopLeft": Qt.SizeFDiagCursor,
                "BottomRight": Qt.SizeFDiagCursor,
                "TopRight": Qt.SizeBDiagCursor,
                "BottomLeft": Qt.SizeBDiagCursor
            }
            self.setCursor(cursors.get(edge, Qt.ArrowCursor))
            self.update()
        except Exception as e:
            logger.warn(f"[FuturisticWindow] _update_cursor erro: {e}")

    def _perform_resize(self, global_pos: QPoint):
        try:
            from PyQt5.QtCore import QRect as _QRect
            geo = _QRect(self._start_geo)
            delta = global_pos - self._start_mouse

            minw = max(680, self.minimumWidth())
            minh = max(420, self.minimumHeight())

            if "Left" in self._resize_edge:
                new_left = geo.left() + delta.x()
                max_left = geo.right() - minw
                new_left = min(new_left, max_left)
                geo.setLeft(new_left)

            if "Right" in self._resize_edge:
                new_right = geo.right() + delta.x()
                min_right = geo.left() + minw
                new_right = max(new_right, min_right)
                geo.setRight(new_right)

            if "Top" in self._resize_edge:
                new_top = geo.top() + delta.y()
                max_top = geo.bottom() - minh
                new_top = min(new_top, max_top)
                geo.setTop(new_top)

            if "Bottom" in self._resize_edge:
                new_bottom = geo.bottom() + delta.y()
                min_bottom = geo.top() + minh
                new_bottom = max(new_bottom, min_bottom)
                geo.setBottom(new_bottom)

            self.setGeometry(geo)
        except Exception as e:
            logger.error(f"[FuturisticWindow] _perform_resize erro: {e}")

    def _try_enable_mica_or_acrylic(self):
        try:
            if not getattr(self, "_mica_enabled", False):
                return

            hwnd = int(self.winId())
            dwm = ctypes.windll.dwmapi
            DWMWA_SYSTEMBACKDROP_TYPE = 38
            DWMWA_MICA_EFFECT = 1029
            DWM_SBT_MAINWINDOW = 2

            backdrop = ctypes.c_int(DWM_SBT_MAINWINDOW)
            dwm.DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), ctypes.sizeof(backdrop))

            mica_enabled = ctypes.c_int(1)
            dwm.DwmSetWindowAttribute(hwnd, DWMWA_MICA_EFFECT, ctypes.byref(mica_enabled), ctypes.sizeof(mica_enabled))
            logger.info("[FuturisticWindow] Mica/Acrylic nativo habilitado (se suportado).")
        except Exception as e:
            logger.warn(f"[FuturisticWindow] Mica/Acrylic nativo indisponível, usando fallback: {e}")

    def showEvent(self, e):
        try:
            super().showEvent(e)
            if self.windowOpacity() < 0.01:
                self.setWindowOpacity(1.0)
        except Exception as ex:
            logger.warning(f"[FuturisticWindow] showEvent erro: {ex}")

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        w = FuturisticWindow()
        w.setStyleSheet(get_style_sheet())
        w.resize(1100, 700)
        w.show()
        sys.exit(app.exec_())
    except Exception as e:
        logger.error(f"[main] erro: {e}")
