import time

from qtpy.QtCore import QThread
from qtpy.QtCore import Signal

class AIWorker(QThread):
    finished = Signal(str)
    error = Signal(Exception)

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