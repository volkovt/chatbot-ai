import sys
import resources_rc

from PyQt5.QtWidgets import QApplication

from presentation.main_window import MainWindow

if __name__ == "__main__":
    import infra.logging_service as logsvc
    logsvc.configure_logging()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())



