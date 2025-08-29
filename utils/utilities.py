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
    Obtém o caminho base do aplicativo, considerando se está empacotado (frozen) ou não.

    :return: Caminho base do aplicativo.
    """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        print('Base path:', base_path)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.join(base_path, "..")
    return base_path

@lru_cache(maxsize=1)
def get_style_sheet(file_path: str = "presentation/styles/app_styles.qss") -> str:
    """
    Carrega o stylesheet QSS a partir de um arquivo.

    Se o aplicativo estiver empacotado (frozen), o caminho base será sys._MEIPASS;
    caso contrário, usa o diretório atual.

    :param file_path: Caminho relativo para o arquivo QSS.
    :return: Conteúdo do stylesheet ou string vazia se não encontrado.
    """
    try:
        BASE_PATH = get_base_path()
        full_path = os.path.join(os.path.normpath(BASE_PATH), os.path.normpath(file_path))
        logger.info(f"Loading stylesheet from: {full_path}")
        with open(full_path, "r", encoding="utf-8") as file:
            qss = file.read()

            for name, hexcolor in COLOR_VARS.items():
                qss = qss.replace(f"@{name}", hexcolor)

            logger.info(f"[qss] f{qss}")
            return qss
    except FileNotFoundError:
        print(f"Stylesheet file not found: {file_path}")
        return ""
    except UnicodeDecodeError as e:
        print(f"Error reading stylesheet: {e}")
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