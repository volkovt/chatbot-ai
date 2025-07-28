import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from pythonjsonlogger import jsonlogger

def configure_logging(log_dir: str = "logs"):
    os.makedirs(log_dir, exist_ok=True)

    console_handler = logging.StreamHandler(sys.stdout)
    console_fmt = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    console_handler.setFormatter(console_fmt)

    file_path = os.path.join(log_dir, "app.log")
    file_handler = RotatingFileHandler(
        file_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(console_fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console_handler)
    root.addHandler(file_handler)