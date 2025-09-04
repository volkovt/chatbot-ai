import logging
import os
import sys
from datetime import date, datetime
from functools import lru_cache

from presentation.editor.syntax import LEXER_BY_EXT

logger = logging.getLogger("Utilities")

COLOR_VARS = {
    "bgdark":      "#1e1e1e",
    "bg":           "#282828",
    "bglight":     "#333333",
    "hover":        "#444444",
    "border":       "#555555",
    "text":         "#ffffff",
    "accent":       "#ff9900",
    "accentlight": "#ffaa00",
    "accentdark":  "#ff7700",
    "disabled":     "#A35C5C",
}

def get_base_path() -> str:
    """
    Caminho base do aplicativo, compatível com PyInstaller e Nuitka.
    """
    try:
        if getattr(sys, "frozen", False):
            if hasattr(sys, "_MEIPASS"):
                return sys._MEIPASS
            return os.path.dirname(sys.executable)
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(here, "..")
    except Exception as e:
        print("Erro ao resolver base path:", e)
        return os.getcwd()

@lru_cache(maxsize=1)
@lru_cache(maxsize=1)
def get_style_sheet(file_path: str = "presentation/styles/app_styles.qss") -> str:
    """
    Carrega o stylesheet QSS a partir de um arquivo.
    Funciona em modo desenvolvimento e quando empacotado com Nuitka ou PyInstaller.

    :param file_path: Caminho relativo para o arquivo QSS.
    :return: Conteúdo do stylesheet ou string vazia se não encontrado.
    """
    try:
        # Obter o caminho base (compatível com dev, PyInstaller e Nuitka)
        base_path = get_base_path()

        # Construir caminho completo
        full_path = os.path.join(base_path, file_path)
        logger.info(f"Loading stylesheet from: {full_path}")

        with open(full_path, "r", encoding="utf-8") as file:
            qss = file.read()

            # Substituir variáveis de cores
            for name, hexcolor in COLOR_VARS.items():
                qss = qss.replace(f"@{name}", hexcolor)

            # Corrigir problema de log
            logger.info("[qss] Stylesheet carregado com sucesso")
            return qss

    except FileNotFoundError:
        # Tentativa alternativa para compilações com Nuitka (que pode ter estrutura diferente)
        if getattr(sys, "frozen", False) and not hasattr(sys, "_MEIPASS"):
            try:
                alt_path = os.path.join(os.path.dirname(sys.executable), file_path)
                logger.info(f"Tentando caminho alternativo: {alt_path}")
                with open(alt_path, "r", encoding="utf-8") as file:
                    qss = file.read()
                    for name, hexcolor in COLOR_VARS.items():
                        qss = qss.replace(f"@{name}", hexcolor)
                    return qss
            except FileNotFoundError:
                pass

        logger.error(f"Stylesheet não encontrado: {file_path}")
        print(f"Stylesheet file not found: {file_path}")
        return ""
    except UnicodeDecodeError as e:
        logger.error(f"Erro ao ler stylesheet: {e}")
        print(f"Error reading stylesheet: {e}")
        return ""
    except Exception as e:
        logger.error(f"Erro inesperado ao carregar stylesheet: {e}")
        print(f"Unexpected error loading stylesheet: {e}")
        return ""

def ensure_date(val):
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val).date()
        except Exception:
            return date.today()
    return date.today()

def guess_alias_from_path(path: str) -> str:
    try:
        ext = os.path.splitext(path)[1].lower()
        alias = LEXER_BY_EXT.get(ext, "text")
        logger.info(f"[Syntax] path={path} ext={ext} alias={alias}")
        return alias
    except Exception as e:
        logger.error(f"[Syntax] guess_alias_from_path erro: {e}")
        return "text"