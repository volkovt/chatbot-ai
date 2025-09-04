# apply_qtpy_migration.py
import sys
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("[QtPyMigrator]")

ROOT = Path(__file__).parent

PY_FILES = list(ROOT.rglob("*.py"))

# Padrões de substituição
RE_IMPORT_PYQT5 = re.compile(r"from\s+PyQt5(?:\.[A-Za-z0-9_]+)?\s+import\s+([^\n]+)")
RE_IMPORT_PYQT5_MODULE = re.compile(r"import\s+PyQt5(?:\.[A-Za-z0-9_]+)?\s+as\s+([A-Za-z0-9_]+)")
RE_FROM_PYQT5 = re.compile(r"from\s+PyQt5\s+import\s+([^\n]+)")

RE_SIGNAL = re.compile(r"\bpyqtSignal\b")
RE_SLOT = re.compile(r"\bpyqtSlot\b")
RE_PROPERTY = re.compile(r"\bpyqtProperty\b")

RE_SIP = re.compile(r"\bsip\b")
RE_SHIBOKEN = re.compile(r"\bfrom\s+shiboken2\s+import\b|\bfrom\s+shiboken6\s+import\b|\bimport\s+shiboken2\b|\bimport\s+shiboken6\b")

RE_WEBENGINE_PYQT5 = re.compile(r"from\s+PyQt5\.QtWebEngineWidgets\s+import\s+([^\n]+)")
RE_WEBENGINE_QTPY = re.compile(r"from\s+qtpy\s+import\s+QtWebEngineWidgets")

RE_QT_IMPORTS = re.compile(r"from\s+(qtpy|PyQt5)\s+import\s+Qt(Core|Gui|Widgets|WebEngineWidgets)")

FILES_TO_SKIP = {"qt_compat.py", "apply_qtpy_migration.py", "__init__.py"}

def normalize_qt_imports(text: str) -> str:
    # 1) Trocar imports explícitos de PyQt5 → qtpy
    text = RE_IMPORT_PYQT5.sub(r"from qtpy import \1", text)
    text = RE_IMPORT_PYQT5_MODULE.sub(r"from qtpy import \1", text)
    text = RE_FROM_PYQT5.sub(r"from qtpy import \1", text)

    # 2) Sinais/Slots/Property
    text = RE_SIGNAL.sub("Signal", text)
    text = RE_SLOT.sub("Slot", text)
    text = RE_PROPERTY.sub("Property", text)

    # 3) WebEngine
    text = RE_WEBENGINE_PYQT5.sub(r"from qtpy import QtWebEngineWidgets", text)

    # 4) Remove usos diretos de sip/shiboken (ideal é não depender)
    # (não apagamos importações úteis; apenas avisamos)
    if RE_SIP.search(text):
        logger.warn("Aviso: Encontrado 'sip' em um arquivo — revise manualmente se necessário.")

    return text

HEADER_COMPAT_HINT = (
    "from qt_compat import QtCore, QtGui, QtWidgets, Signal, Slot, Property, QtWebEngineWidgets\n"
)

def ensure_compat_header(text: str) -> str:
    # Se já importa via qt_compat, não duplica
    if "from qt_compat import " in text:
        return text

    # Insere após primeiros imports do Qt/qtpy, se houver
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines[:20]):  # primeira janela de imports
        if RE_QT_IMPORTS.search(line) or "from qtpy import" in line:
            insert_at = i + 1

    lines.insert(insert_at, HEADER_COMPAT_HINT.rstrip())
    return "\n".join(lines)

def process_file(path: Path):
    if path.name in FILES_TO_SKIP:
        return
    try:
        original = path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Falha lendo {path}: {e}")
        return

    text = original

    text = normalize_qt_imports(text)

    # Heurística: se o arquivo usa Qt, garante cabeçalho compat
    if ("QtCore" in text or "QtWidgets" in text or "QtGui" in text or "QtWebEngine" in text) \
        and "qt_compat" not in text:
        text = ensure_compat_header(text)

    if text != original:
        backup = path.with_suffix(path.suffix + ".bak")
        try:
            backup.write_text(original, encoding="utf-8")
            path.write_text(text, encoding="utf-8")
            logger.info(f"Atualizado: {path} (backup em {backup.name})")
        except Exception as e:
            logger.error(f"Erro escrevendo {path}: {e}")
    else:
        logger.info(f"Sem mudanças: {path}")

def main():
    logger.info(f"Iniciando migração em {ROOT}")
    for py in PY_FILES:
        process_file(py)
    logger.info("Concluído. Revise os avisos e faça um teste de execução.")

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)
        sys.exit(1)
