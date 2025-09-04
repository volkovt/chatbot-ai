# qt_compat.py
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("[QtCompat]")

try:
    # Define o backend Qt a partir do QtPy
    os.environ.setdefault("QT_API", "pyside6")

    # Imports centrais via QtPy
    from qtpy import QtCore, QtGui, QtWidgets
    from qtpy.QtCore import Signal, Slot, Property

    # Opcional: WebEngine (só se seu projeto usa)
    try:
        from qtpy import QtWebEngineWidgets  # noqa: F401
        # Inicialização do WebEngine no PySide6 →
        try:
            from PySide6.QtWebEngineCore import QtWebEngineCore
            QtWebEngineCore.initialize()
        except Exception:
            pass
    except Exception:
        QtWebEngineWidgets = None  # para permitir import mesmo sem WebEngine

except Exception as e:
    logger.error(f"[QtCompat] Erro ao carregar backend Qt/QtPy: {e}", exc_info=True)
    raise

__all__ = [
    "QtCore",
    "QtGui",
    "QtWidgets",
    "Signal",
    "Slot",
    "Property",
    "QtWebEngineWidgets",
]
