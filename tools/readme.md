# Migração PyQt5 → PySide6 (via QtPy) + Nuitka

Guia rápido para converter seus apps PyQt5 existentes em projetos compatíveis com PySide6 e empacotamento com Nuitka — com o mínimo de mudanças, preservando arquitetura, logs e estabilidade.

---

## Objetivo do guia

* Padronizar **imports** para `qtpy` (camada de compatibilidade).
* Trocar **PyQt5** por **PySide6** sem reescrever a UI.
* Garantir **build** sólido com **Nuitka** (incluindo QtWebEngine).
* Manter **boas práticas** (logs, try/except, desacoplamento).

---

## 1) Dependências

Instale:

```
pip install qtpy PySide6
# Se usar WebEngine:
pip install PySide6-Addons PySide6-Essentials
```

Remova ao final da migração:

```
pip uninstall PyQt5 PyQt5-sip
```

Sugestão de linhas mínimas no `requirements.txt`:

```
qtpy>=2.4
PySide6>=6.7
setuptools
wheel
nuitka
ordered-set
zstandard
qtawesome
# Se usar WebEngine:
PySide6-Addons>=6.6
PySide6-Essentials>=6.6
```

---

## 2) Padronize imports para `qtpy`

### Antes (PyQt5)

```python
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QUrl
```

### Depois (QtPy + PySide6)

```python
from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Signal, Slot, QUrl
```

### Regras rápidas

* `pyqtSignal` → `Signal`
* `pyqtSlot` → `Slot`
* `pyqtProperty` → `Property` (de `qtpy.QtCore`)
* Se precisar de WebEngine:

  ```python
  from qtpy import QtWebEngineWidgets
  ```

> Dica: crie um **módulo de compatibilidade** único (ex.: `qt_compat.py`) que exporte `QtCore`, `QtGui`, `QtWidgets`, `Signal`, `Slot` e `QtWebEngineWidgets`. Em todos os arquivos da UI, importe **apenas** a partir dele. Isso facilita manutenção e futura troca de backend.

---

## 3) Sinais, Slots e Dialogs

### Sinais/slots

```python
from qtpy import QtWidgets
from qtpy.QtCore import Signal, Slot
import logging

logger = logging.getLogger("[MinhaView]")

class MinhaView(QtWidgets.QWidget):
    dadoPronto = Signal(str)

    @Slot(str)
    def on_dado(self, s: str):
        try:
            logger.info("Processando dado")
            # ...
        except Exception as e:
            logger.error(f"Falha em on_dado: {e}", exc_info=True)
```

### QFileDialog (retornos)

```python
fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Abrir", "", "Todos (*.*)")
if fname:
    # use fname
    ...
```

---

## 4) QtWebEngine (se aplicável)

* Importe com `qtpy`:

  ```python
  from qtpy import QtWebEngineWidgets
  ```

* No PySide6, inicialize cedo quando necessário:

  ```python
  try:
      from PySide6.QtWebEngineCore import QtWebEngineCore
      QtWebEngineCore.initialize()
  except Exception:
      pass
  ```

* Em **build standalone** (Nuitka), garanta variáveis de ambiente do WebEngine (paths de recursos/locais/processo). Um padrão robusto usa `QLibraryInfo` para descobrir caminhos e exportá-los ao iniciar o app (exemplo inspirado no seu `main.py`).&#x20;

---

## 5) Recursos (.qrc) e estilos (.qss)

* Recompile seus `.qrc` para `.py` com:

  ```
  pyside6-rcc resources.qrc -o resources_rc.py
  ```
* Inclua `.qss`, ícones e HTML/JS no empacotamento via Nuitka (ver seção 7).

---

## 6) Entry point com logs e robustez

```python
import os, sys, logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("[Main]")

os.environ.setdefault("QT_API", "pyside6")  # garante backend do QtPy

from qtpy import QtWidgets

def main():
    try:
        app = QtWidgets.QApplication(sys.argv)
        from presentation.main_window import MainWindow
        w = MainWindow()
        w.show()
        logger.info("Aplicação iniciada")
        return app.exec()
    except Exception as e:
        logger.error(f"Falha ao iniciar: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
```

> Padrão: **sempre** logs (`logger.info/error/warn`) e **try/except** em pontos críticos (bootstrap, threads, slots intensivos).

---

## 7) Build com Nuitka (Qt)

### Flags essenciais

* `--standalone` e `--onefile` (se desejar um único executável).
* `--enable-plugin=qt-plugins` para capturar binários Qt.
* `--qt-plugins=platforms,styles,svg,iconengines,imageformats,network,webengine` conforme uso.
* Inclua assets:

  * `--include-data-files=app_styles.qss=app_styles.qss`
  * `--include-data-dir=resources=resources`
* Evite importar toolkits não usados:

  * `--nofollow-import-to=PyQt5,PyQt6,PySide2`

### Exemplo (Windows, PowerShell/CMD)

```
nuitka main.py ^
  --standalone ^
  --onefile ^
  --enable-plugin=qt-plugins ^
  --qt-plugins=platforms,styles,svg,iconengines,imageformats,network,webengine ^
  --nofollow-import-to=PyQt5,PyQt6,PySide2 ^
  --include-data-files=app_styles.qss=app_styles.qss ^
  --include-data-dir=resources=resources ^
  --remove-output
```

> Se **não** usa WebEngine, remova `webengine` e as dependências Addons.

---

## 8) Estrutura sugerida de compatibilidade

`qt_compat.py` centraliza variações de backend e inicialização do WebEngine:

```python
# qt_compat.py
import os, logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("[QtCompat]")

os.environ.setdefault("QT_API", "pyside6")

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Signal, Slot, Property
try:
    from qtpy import QtWebEngineWidgets  # opcional
    try:
        from PySide6.QtWebEngineCore import QtWebEngineCore
        QtWebEngineCore.initialize()
    except Exception:
        pass
except Exception:
    QtWebEngineWidgets = None

__all__ = ["QtCore", "QtGui", "QtWidgets", "Signal", "Slot", "Property", "QtWebEngineWidgets"]
```

Em todo o projeto:

```python
from qt_compat import QtCore, QtGui, QtWidgets, Signal, Slot, QtWebEngineWidgets
```

---

## 9) Pitfalls comuns e como evitar

1. **Uso de `sip`**

   * Remova dependências diretas (`sip.setapi`, `sip.isdeleted`, etc.).
   * Se absolutamente necessário, substitua por `shiboken6` — mas priorize eliminar dependência.

2. **Imports mistos**

   * Nunca misture `from PyQt5...` com `from qtpy...`. Padronize **tudo** para `qtpy`.

3. **QtWebEngine em standalone**

   * Sem variáveis de ambiente corretas, páginas podem não carregar ou o processo não iniciar. Configure paths de `QtWebEngineProcess`, `resources` e `locales` na inicialização (vide seção 4; referência nos seus exemplos).&#x20;

4. **Arquivos de dados ausentes**

   * `.qss`, ícones, HTML/JS precisam ser incluídos via `--include-data-*`. Teste executável “limpo” (fora do repositório) para garantir que tudo foi empacotado.

5. **QThreads e sinais**

   * Emite sinais apenas a partir de workers; conecte/valide assinaturas com `@Slot(...)`. Sempre proteja blocos críticos com `try/except` + `logger.error(..., exc_info=True)`.

---

## 10) Checklist final de migração

* [ ] `pip install qtpy PySide6` (+ Addons/Essen. se usar WebEngine).
* [ ] Remover `PyQt5` do projeto/ambiente.
* [ ] Trocar **todos** imports para `qtpy` (ou importar de `qt_compat.py`).
* [ ] `pyqtSignal/pyqtSlot/pyqtProperty` → `Signal/Slot/Property`.
* [ ] Ajustar `QtWebEngine` (imports e init).
* [ ] Recompilar `.qrc` com `pyside6-rcc`.
* [ ] Garantir logs e `try/except` no bootstrap, threads e slots.
* [ ] Ver flags do Nuitka (plugins Qt, data files/dirs).
* [ ] Testar o executável standalone em pasta “limpa”.
* [ ] Escrever “Notas de build” no repositório (ex.: versões do MSVC/VC++ no Windows, se necessário).

---

## 11) Modelo de seção “Build” no seu README do app

```
### Build (Nuitka)

1) Ambiente:
   - Python 3.10+ (recomendado)
   - pacotes: qtpy, PySide6, (PySide6-Addons/Essen. se usar WebEngine), nuitka

2) Recursos:
   pyside6-rcc resources.qrc -o resources_rc.py

3) Empacotar:
   nuitka main.py --standalone --onefile --enable-plugin=qt-plugins \
     --qt-plugins=platforms,styles,svg,iconengines,imageformats,network,webengine \
     --nofollow-import-to=PyQt5,PyQt6,PySide2 \
     --include-data-files=app_styles.qss=app_styles.qss \
     --include-data-dir=resources=resources \
     --remove-output
```

---

## 12) Boas práticas (PyQt/PySide + IA)

* **Clean Architecture**: UI → Casos de Uso → Gateways/Services (IA/HTTP).
* **Desacople a IA** do Qt (facilita testes e troca de fornecedores).
* **Logger** em todos os fluxos críticos (`logger.info`, `logger.warn`, `logger.error`).
* **Tratamento de exceções** consistente (sempre `exc_info=True`).
* **Scripts reutilizáveis** de migração/verificação (ex.: lint que detecta `from PyQt5`).
