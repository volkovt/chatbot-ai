import math
import sys
import logging
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QLinearGradient, QFont, QFontMetricsF, QPen, QPainterPathStroker
)
from PySide6.QtWidgets import QApplication, QWidget, QMainWindow

# ---------- Logging ----------
logger = logging.getLogger("Itauloader")
logger.setLevel(logging.INFO)
h = logging.StreamHandler(sys.stdout)
h.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(h)

# ---------- Cores/UI ----------
BG_TOP = QColor("#0A2D74")
BG_BOTTOM = QColor("#061E53")
BORDER = QColor("#113985")
BLOCK = QColor("#FFC20E")
TEXT_SHADOW = QColor(0, 0, 0, int(0.18 * 255))
BADGE_RX = 42
PADDING = 36

# ---------- Timeline ----------
COLS = 24          # mais fino p/ não “pular” traços
ROWS = 14
STEP_MS = 14       # atraso entre blocos (construção)
HOLD_MS = 900
BREATH_MS = 3400
BLOCK_GAP = 1.5    # respiro interno

TITLE_TEXT = "Itaú"
TITLE_FONT_FAMILY = "Segoe UI"
TITLE_WEIGHT = 800
TITLE_PT = 94

class BlockLoaderWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.cols, self.rows = COLS, ROWS
        self.step_ms, self.hold_ms = STEP_MS, HOLD_MS
        self.elapsed_ms = 0

        self.cells = []         # QRectF dos blocos válidos (apenas dentro do texto)
        self.total_blocks = 0
        self.build_time = 0
        self.cycle_ms = 0

        self._rebuild_paths()

        self.timer = QTimer(self)
        self.timer.setInterval(16)     # ~60fps
        self.timer.timeout.connect(self._on_tick)
        self.timer.start()

    # --------- Layout/paths ---------
    def _build_text_path(self):
        self.text_path = QPainterPath()
        font = QFont(TITLE_FONT_FAMILY, TITLE_PT, TITLE_WEIGHT)
        fm = QFontMetricsF(font)
        text_w = max(1.0, fm.horizontalAdvance(TITLE_TEXT))
        target_w = max(1.0, self.badge_rect.width() * 0.75)
        scale = target_w / text_w
        font.setPointSizeF(max(8.0, TITLE_PT * scale))
        self.font = font

        fm = QFontMetricsF(self.font)
        text_w = fm.horizontalAdvance(TITLE_TEXT)
        text_h = fm.ascent()
        x = self.badge_rect.center().x() - text_w / 2
        y = self.badge_rect.center().y() + text_h / 2
        self.text_path.addText(QPointF(x, y), self.font, TITLE_TEXT)

        # “engrossa” um pouco o path para capturar blocos nas bordas finas
        stroker = QPainterPathStroker()
        stroker.setWidth(1.0)  # 1px de stroke virtual
        outline = stroker.createStroke(self.text_path)
        self.fill_path = self.text_path.united(outline)

    def _rebuild_paths(self):
        w = max(2.0, self.width())
        h = max(2.0, self.height())
        self.badge_rect = QRectF(PADDING, PADDING, w - 2*PADDING, h - 2*PADDING)

        self._build_text_path()

        tb = self.fill_path.boundingRect()
        cell_w = tb.width() / self.cols
        cell_h = tb.height() / self.rows + 4
        cell = max(0.5, min(cell_w, cell_h))
        block_size = max(0.5, cell - BLOCK_GAP)
        origin = QPointF(
            tb.left() + (tb.width() - self.cols * cell) / 2,
            tb.top()  + (tb.height() - self.rows * cell) / 2
        )

        # monta células e filtra por interseção real do retângulo com o path
        cells = []
        rect_path = QPainterPath()
        for c in range(self.cols):
            for r in range(self.rows):
                x = origin.x() + c * cell + (cell - block_size) / 2
                y = origin.y() + r * cell + (cell - block_size) / 2
                rect = QRectF(x, y, block_size, block_size)

                rect_path = QPainterPath()
                rect_path.addRect(rect)

                # Critérios: qualquer interseção OU center/cantos contidos.
                if (self.fill_path.intersects(rect_path)
                    or self.fill_path.contains(QPointF(x + block_size/2, y + block_size/2))
                    or self.fill_path.contains(QPointF(x+0.1, y+0.1))
                    or self.fill_path.contains(QPointF(x+block_size-0.1, y+0.1))
                    or self.fill_path.contains(QPointF(x+0.1, y+block_size-0.1))
                    or self.fill_path.contains(QPointF(x+block_size-0.1, y+block_size-0.1))):
                    cells.append(rect)

        # ordena: esquerda→direita (x asc), baixo→cima (y desc)
        cells.sort(key=lambda r: (round(r.x(), 3), -round(r.y(), 3)))

        self.cells = cells
        self.total_blocks = max(1, len(self.cells))
        self.build_time = self.total_blocks * self.step_ms
        self.cycle_ms = self.build_time + self.hold_ms + self.build_time

        logger.info("Blocos úteis: %d (grid %dx%d)", self.total_blocks, self.cols, self.rows)

    def resizeEvent(self, _ev):
        self._rebuild_paths()

    # --------- Timeline ---------
    def _on_tick(self):
        self.elapsed_ms = (self.elapsed_ms + self.timer.interval()) % self.cycle_ms
        self.update()

    def _active_count(self) -> int:
        t = self.elapsed_ms
        if t < self.build_time:
            return int(t // self.step_ms) + 1
        t -= self.build_time
        if t < self.hold_ms:
            return self.total_blocks
        t -= self.hold_ms
        off = int(t // self.step_ms) + 1
        return max(0, self.total_blocks - off)

    # --------- Pintura ---------
    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # fundo
        grad = QLinearGradient(self.rect().topLeft(), self.rect().bottomRight())
        grad.setColorAt(0.0, BG_TOP); grad.setColorAt(1.0, BG_BOTTOM)
        p.fillRect(self.rect(), grad)

        # respiração
        phase = (self.elapsed_ms % BREATH_MS) / BREATH_MS
        scale = 1.0 + 0.012 * math.sin(2 * math.pi * phase)

        p.save()
        cx, cy = self.badge_rect.center().x(), self.badge_rect.center().y()
        p.translate(cx, cy); p.scale(scale, scale); p.translate(-cx, -cy)

        # borda
        p.setPen(QPen(BORDER, 6)); p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.badge_rect, BADGE_RX, BADGE_RX)

        # clip no texto
        p.save()
        p.setClipPath(self.fill_path)

        # desenha blocos
        active = self._active_count()
        p.setPen(Qt.NoPen); p.setBrush(BLOCK)
        for i in range(min(active, self.total_blocks)):
            p.drawRect(self.cells[i])

        p.restore()

        # sombra do texto
        p.setPen(Qt.NoPen); p.setBrush(TEXT_SHADOW)
        p.drawPath(self.fill_path)

        p.restore()
        p.end()

class LoaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Itaú Loader")
        self.setStyleSheet("background: #061E53;")
        self.widget = BlockLoaderWidget(self)
        self.setCentralWidget(self.widget)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.resize(600, 600)
        # self.showFullScreen()

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape:
            self.close()

def main():
    try:
        app = QApplication(sys.argv)
        win = LoaderWindow()
        win.show()
        sys.exit(app.exec())
    except Exception as e:
        logger.error("Erro fatal: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
