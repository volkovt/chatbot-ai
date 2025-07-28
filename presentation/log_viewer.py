import logging
import os
import json
import time
from datetime import datetime, timedelta
from collections import deque

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QSizePolicy, QHeaderView, QLabel, QComboBox,
    QTextEdit, QSplitter, QLineEdit, QDateTimeEdit, QTabWidget,
    QWidget, QFileDialog, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QBrush, QColor, QCursor
import qtawesome as qta
from utils.utilities import get_style_sheet, COLOR_VARS, logger


class LogEntry:
    """Classe simples para armazenar logs lidos do arquivo."""
    def __init__(self, timestamp, name, levelname, message):
        self.timestamp = timestamp
        self.name = name
        self.levelname = levelname
        self.message = message

    def getMessage(self):
        return self.message


class QtLogHandler(logging.Handler, QObject):
    """Handler que emite registros de log como sinais Qt."""
    new_record = pyqtSignal(logging.LogRecord)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setLevel(logging.DEBUG)

    def emit(self, record):
        try:
            self.new_record.emit(record)
        except Exception:
            self.handleError(record)


class LogPage(QWidget):
    """Página de visualização de logs (arquivo estático)."""
    def __init__(self, title, log_file_path):
        super().__init__()
        self.log_file_path = log_file_path
        self.records = []
        self.last_key = None
        self.last_row = None
        self._init_ui()
        self.load_from_file()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar...")
        self.search_input.textChanged.connect(self._apply_all_filters)
        self.filter_layout.addWidget(self.search_input)

        self.start_dt = QDateTimeEdit(self)
        self.start_dt.setCalendarPopup(True)
        self.start_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_dt.setDateTime(datetime.fromtimestamp(0))
        self.start_dt.dateTimeChanged.connect(self._apply_all_filters)
        self.filter_layout.addWidget(QLabel("De:"))
        self.filter_layout.addWidget(self.start_dt)

        self.end_dt = QDateTimeEdit(self)
        self.end_dt.setCalendarPopup(True)
        self.end_dt.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_dt.setDateTime(datetime.now() + timedelta(days=1))
        self.end_dt.dateTimeChanged.connect(self._apply_all_filters)
        self.filter_layout.addWidget(QLabel("Até:"))
        self.filter_layout.addWidget(self.end_dt)

        filter_label = QLabel("Nível:")
        filter_label.setStyleSheet(f"color: {COLOR_VARS['text']};")
        self.filter_layout.addWidget(filter_label)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Todos", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.filter_combo.currentTextChanged.connect(self._apply_all_filters)
        self.filter_layout.addWidget(self.filter_combo)

        self.filter_layout.addStretch()
        layout.addLayout(self.filter_layout)

        self.btn_layout = QHBoxLayout()
        self.clear_button = QPushButton("Limpar Logs")
        self.clear_button.setIcon(qta.icon("fa5s.broom", color=COLOR_VARS["accent"]))
        self.clear_button.clicked.connect(self._clear_logs)
        self.btn_layout.addWidget(self.clear_button)

        self.reload_button = QPushButton("Recarregar")
        self.reload_button.setIcon(qta.icon("fa5s.sync", color=COLOR_VARS["accent"]))
        self.reload_button.clicked.connect(self.load_from_file)
        self.btn_layout.addWidget(self.reload_button)

        self.btn_layout.addStretch()
        layout.addLayout(self.btn_layout)

        splitter = QSplitter(Qt.Vertical)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Timestamp", "Logger", "Nível", "Mensagem", "Count"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._update_message_view)
        splitter.addWidget(self.table)

        self.message_viewer = QTextEdit()
        self.message_viewer.setReadOnly(True)
        splitter.addWidget(self.message_viewer)
        splitter.setSizes([400, 200])
        layout.addWidget(splitter)

    def load_from_file(self):
        self._clear_logs()
        if not self.log_file_path or not os.path.exists(self.log_file_path):
            return
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        ts = data.get('asctime')
                        name = data.get('name')
                        lvl = data.get('levelname')
                        msg = data.get('message')
                        entry = LogEntry(ts, name, lvl, msg)
                        self._insert_record(entry)
                    except Exception:
                        continue
            self._apply_all_filters()
        except Exception as e:
            logging.getLogger().error(
                f"[LogPage] falha ao carregar arquivo {self.log_file_path}: {e}",
                exc_info=True
            )

    def _insert_record(self, record):
        key = (getattr(record, 'name', ''), getattr(record, 'levelname', ''), record.getMessage())
        if key == self.last_key:
            try:
                count_item = self.table.item(self.last_row, 4)
                new_count = int(count_item.text()) + 1
                count_item.setText(str(new_count))
                return
            except Exception:
                pass
        self.records.insert(0, record)
        self.table.insertRow(0)
        ts = getattr(record, 'timestamp', None) or \
             datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        name = getattr(record, 'name', '')
        lvl = getattr(record, 'levelname', '')
        msg = record.getMessage()
        items = [
            QTableWidgetItem(ts),
            QTableWidgetItem(name),
            QTableWidgetItem(lvl),
            QTableWidgetItem(msg),
            QTableWidgetItem("1")
        ]
        color = COLOR_VARS["accentlight"] if lvl in ("ERROR", "CRITICAL") else COLOR_VARS["accent"]
        items[2].setForeground(QBrush(QColor(color)))
        for col, item in enumerate(items):
            self.table.setItem(0, col, item)
        self.last_key = key
        self.last_row = 0

    def _apply_all_filters(self):
        text = self.search_input.text().lower()
        level = self.filter_combo.currentText()
        start = self.start_dt.dateTime().toPyDateTime()
        end = self.end_dt.dateTime().toPyDateTime()
        for i, record in enumerate(self.records):
            msg = record.getMessage()
            lvl = getattr(record, 'levelname', '')
            ts_attr = getattr(record, 'created', None)
            try:
                if ts_attr is None:
                    dt = datetime.fromisoformat(record.timestamp)
                else:
                    dt = datetime.fromtimestamp(ts_attr)
            except Exception:
                dt = None
            cond_search = text in msg.lower()
            cond_level = (level == "Todos" or lvl == level)
            cond_time = (dt and start <= dt <= end) if dt else True
            show = cond_search and cond_level and cond_time
            self.table.setRowHidden(i, not show)

    def _update_message_view(self):
        selected = self.table.selectionModel().selectedRows()
        if selected:
            row = selected[0].row()
            self.message_viewer.setPlainText(self.records[row].getMessage())
        else:
            self.message_viewer.clear()

    def _clear_logs(self):
        self.table.setRowCount(0)
        self.records.clear()
        self.last_key = None
        self.last_row = None
        self.message_viewer.clear()


class LiveLogPage(LogPage):
    """Página de logs em tempo real com perfil de performance."""
    def __init__(self):
        super().__init__("Live", None)
        self.reload_button.setVisible(False)
        self._handler = QtLogHandler()
        root = logging.getLogger()
        root.addHandler(self._handler)
        self._handler.new_record.connect(self._handle_live_record)
        self._timestamps = deque(maxlen=1000)
        self.rate_label = QLabel("Logs/s: 0")
        self.rate_label.setStyleSheet(f"color: {COLOR_VARS['text']};")
        self.btn_layout.insertWidget(self.btn_layout.count()-1, self.rate_label)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_rate)
        self._timer.start(1000)

    def _handle_live_record(self, record):
        """Envia registro em tempo real para a UI e atualiza filtro de tempo."""
        self._insert_record(record)
        self._timestamps.append(time.time())
        self.end_dt.setDateTime(datetime.now() + timedelta(days=1))
        self._apply_all_filters()

    def _update_rate(self):
        now = time.time()
        count = sum(1 for t in self._timestamps if t >= now - 1)
        self.rate_label.setText(f"Logs/s: {count}")


class LogViewerDialog(QDialog):
    """Diálogo principal com abas para múltiplos arquivos e logs ao vivo."""
    def __init__(self, parent=None):
        super().__init__(parent)
        flags = self.windowFlags()
        flags |= Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint
        self.setWindowFlags(flags)
        self.setWindowTitle("Visualizador de Logs")
        self.resize(900, 700)
        self.setStyleSheet(get_style_sheet())

        self.layout = QVBoxLayout(self)
        open_layout = QHBoxLayout()
        self.open_button = QPushButton("Abrir Arquivo")
        self.open_button.setIcon(qta.icon("fa5s.folder-open", color=COLOR_VARS["accent"]))
        self.open_button.clicked.connect(self.open_file)
        open_layout.addWidget(self.open_button)
        open_layout.addStretch()
        self.layout.addLayout(open_layout)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.layout.addWidget(self.tabs)
        self.add_live_tab()
        default_path = os.path.join(os.getcwd(), "logs", "app.log")
        self.add_log_tab("app.log", default_path)

    def add_live_tab(self):
        page = LiveLogPage()
        self.tabs.addTab(page, "Live")

    def add_log_tab(self, title, path):
        page = LogPage(title, path)
        self.tabs.addTab(page, title)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Arquivo de Log", os.getcwd(),
            "Log Files (*.log *.txt);;All Files (*)"
        )
        if path:
            title = os.path.basename(path)
            self.add_log_tab(title, path)

    def _close_tab(self, index: int):
        self.tabs.removeTab(index)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            cursor_pos = QCursor.pos()
            desktop = QApplication.desktop()
            screen_index = desktop.screenNumber(cursor_pos)
            geom = desktop.screenGeometry(screen_index)
            self.setGeometry(geom)
            self.setWindowState(self.windowState() | Qt.WindowMaximized)
        except Exception as e:
            logger.error(f"[LogViewerDialog] erro ao maximizar janela: {e}")