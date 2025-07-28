import time

from PyQt5.QtCore import QThread, pyqtSignal


class AIWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(Exception)

    def __init__(self, prompt, context_files):
        super().__init__()
        self.prompt = prompt
        self.context_files = context_files

    def run(self):
        try:
            response = "Simulação de resposta da IA para o prompt: " + self.prompt
            time.sleep(5)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(e)