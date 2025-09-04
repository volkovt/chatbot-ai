@echo off
setlocal EnableExtensions EnableDelayedExpansion

title ChatbotAI - Build Nuitka (BAT)
rem ==============================================================================
rem  ChatbotAI - Nuitka Build Orquestrado via .BAT
rem  - Escolhe Python com libffi (via py launcher) e evita o venv problemático
rem  - Compila resources.qrc
rem  - Executa Nuitka com flags de PySide6/Qt WebEngine
rem  - Pós-build: garante libffi-*.dll no main.dist
rem  - Logs em logs\build_nuitka.log
rem  Variáveis opcionais:
rem    CHATBOTAI_PYTHON      -> caminho do python.exe a usar (sobrepõe detecção)
rem    CHATBOTAI_SKIP_PIP=1  -> pula "pip install -r requirements.txt"
rem ==============================================================================
set "CHATBOTAI_SKIP_PIP=0"
set "PROJECT_DIR=%~dp0"
set "ENABLE_OPTIMIZATIONS=1"
set "ONEFILE=1"
set "WINDOWS_CONSOLE_MODE=disable"
set "QT_API=pyside6"
set "MAIN_PATH=main.py"
set "OUTDIR=%PROJECT_DIR%nuitka"
set "DIST=%OUTDIR%\main.dist"
set "OUTNAME=ChatbotAI"

rem ---- Variáveis de build ---------------------------------------------------
echo [BuildNuitkaBAT] Diretório de saída: "%OUTDIR%" >> "%LOG%"
echo [BuildNuitkaBAT] Nome do executável: "%OUTNAME%" >> "%LOG%"
echo [BuildNuitkaBAT] QT_API: "%QT_API%" >> "%LOG%"
echo [BuildNuitkaBAT] Variáveis de build definidas. >> "%LOG%"
echo [BuildNuitkaBAT] Projeto: %PROJECT_DIR% >> "%LOG%"
echo [BuildNuitkaBAT] Main: %MAIN_PATH% >> "%LOG%"
echo [BuildNuitkaBAT] Onefile: %ONEFILE% >> "%LOG%"
echo [BuildNuitkaBAT] Windows console mode: %WINDOWS_CONSOLE_MODE% >> "%LOG%"
echo [BuildNuitkaBAT] CHATBOTAI_SKIP_PIP: %CHATBOTAI_SKIP_PIP% >> "%LOG%"

rem Ir para o diretório do script
pushd "%PROJECT_DIR%" >nul 2>&1

rem ---- Preparação -------------------------------------------------------------

if not exist "logs" mkdir "logs" >nul 2>&1
    if not exist "logs" (
      echo [BuildNuitkaBAT] ERRO: não consegui criar diretório logs.
      exit /b 1
    )
    echo [BuildNuitkaBAT] Diretorio de logs: %PROJECT_DIR%logs
    set "LOG=logs\build_nuitka.log"
    if exist "%LOG%" (
      echo [BuildNuitkaBAT] Limpando log antigo...
      echo [BuildNuitkaBAT] Limpando log antigo... >> "%LOG%"
      del /f /q "%LOG%" >nul 2>&1
    )
    echo [BuildNuitkaBAT] Iniciado em %DATE% %TIME% > "%LOG%"

rem ---- 1) Escolha do Python ----------------------------------------------------
set "PYTHON_EXE="

echo [BuildNuitkaBAT] Detectando Python 3.x com libffi... >> "%LOG%"
if not "%CHATBOTAI_PYTHON%"=="" (
  set "PYTHON_EXE=%CHATBOTAI_PYTHON%"
  echo [BuildNuitkaBAT] PY definido por CHATBOTAI_PYTHON: "%PYTHON_EXE%" >> "%LOG%"
) else (
  for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>NUL') do set "PYTHON_EXE=%%i"
  if "%PYTHON_EXE%"=="" for /f "delims=" %%i in ('python -c "import sys; print(sys.executable)" 2^>NUL') do set "PYTHON_EXE=%%i"
)
rem Verificação libffi
if "%PYTHON_EXE%"=="" (
  echo [BuildNuitkaBAT] ERRO: Python não encontrado. >> "%LOG%"
  exit /b 1
)

echo [BuildNuitkaBAT] Verificando libffi...
echo [BuildNuitkaBAT] Usando Python: "%PYTHON_EXE%" >> "%LOG%"

rem ---- 3) Instalar dependências ------------------------------------------------
echo [BuildNuitkaBAT] Verificando requirements.txt... >> "%LOG%"
if exist "requirements.txt" (
echo [BuildNuitkaBAT] Instalando dependências... >> "%LOG%"
"%PYTHON_EXE%" -m pip install --upgrade pip >> "%LOG%" 2>&1
if errorlevel 1 goto :pip_fail
"%PYTHON_EXE%" -m pip install -r requirements.txt >> "%LOG%" 2>&1
if errorlevel 1 goto :pip_fail
) else (
echo [BuildNuitkaBAT] Aviso: requirements.txt não encontrado. >> "%LOG%"
)
echo [BuildNuitkaBAT] Dependências instaladas. >> "%LOG%"

rem ---- 4) Compilar resources.qrc ----------------------------------------------
echo [BuildNuitkaBAT] Compilando resources.qrc (se existir)...
if exist "resources.qrc" (
  echo [BuildNuitkaBAT] Compilando resources.qrc... >> "%LOG%"
  "%PYTHON_EXE%" -m PySide6.scripts.rcc resources.qrc -o resources_rc.py >> "%LOG%" 2>&1
  if errorlevel 1 (
    rem Fallback para pyside6-rcc no PATH
    pyside6-rcc resources.qrc -o resources_rc.py >> "%LOG%" 2>&1
    if errorlevel 1 (
      echo [BuildNuitkaBAT] Aviso: Falha ao compilar via PySide6.scripts.rcc e pyside6-rcc. Prosseguindo. >> "%LOG%"
    )
  )
) else (
  echo [BuildNuitkaBAT] resources.qrc não encontrado; prosseguindo. >> "%LOG%"
)
echo [BuildNuitkaBAT] resources.qrc processado. >> "%LOG%"

rem ---- Descoberta dinâmica de plugins Qt (via qtpy) ---------------------------
echo [BuildNuitkaBAT] Detectando plugins Qt via qtpy... >> "%LOG%"
set "QT_PLUGINS="
for /f "delims=" %%i in ('%PYTHON_EXE% -c "import os,sys; os.environ.setdefault(\"QT_API\",\"pyside6\"); from pathlib import Path; try: from qtpy.QtCore import QLibraryInfo; LP = getattr(QLibraryInfo,\"LibraryPath\",None); plugins_dir = Path(QLibraryInfo.path(getattr(LP,\"PluginsPath\"))) if LP and hasattr(QLibraryInfo,\"path\") else Path(QLibraryInfo.location(QLibraryInfo.PluginsPath)); fam = sorted([d.name for d in plugins_dir.iterdir() if d.is_dir()]) if plugins_dir.exists() else []; except Exception: fam = []; wish = [\"platforms\",\"styles\",\"imageformats\",\"iconengines\",\"platforminputcontexts\",\"platformthemes\",\"tls\",\"webengine\"]; sel = [f for f in wish if f in set(fam)] or [\"platforms\",\"styles\",\"imageformats\"]; print(\",\".join(sel), end=\"\")" 2^>NUL') do set "QT_PLUGINS=%%i"

echo [BuildNuitkaBAT] QT_PLUGINS detectados via qtpy: %QT_PLUGINS% >> "%LOG%"
if "%QT_PLUGINS%"=="" (
  rem Fallback definitivo se qtpy falhar ou nada for detectado
  set "QT_PLUGINS=platforms,styles,imageformats"
)

echo [BuildNuitkaBAT] Qt plugins detectados: %QT_PLUGINS%>> "%LOG%"

rem ---- 5) Limpar cache (opcional) ---------------------------------------------
if exist ".nuitka-cache" (
  echo [BuildNuitkaBAT] Limpando .nuitka-cache... >> "%LOG%"
  rmdir /s /q ".nuitka-cache" >> "%LOG%" 2>&1
)
if not exist "%OUTDIR%" mkdir "%OUTDIR%" >nul 2>&1
echo [BuildNuitkaBAT] Limpando diretório de saída... >> "%LOG%"
rem ---- 6) Comando Nuitka ------------------------------------------------------
set NUITKA_CMD=%PYTHON_EXE% -m nuitka ^
 --standalone ^
 --enable-plugin=pyside6 ^
 --include-module=ctypes ^
 --include-module=_ctypes ^
 --include-qt-plugins=%QT_PLUGINS% ^
 --include-data-dir=%PROJECT_DIR%resources=resources ^
 --include-data-dir=%PROJECT_DIR%presentation\styles=presentation/styles ^
 --assume-yes-for-downloads ^
 --nofollow-import-to=PyQt5,PyQt5-stubs,PyQtWebEngine ^
 --output-dir=%OUTDIR% ^
 --output-filename=%OUTNAME% ^
 %MAIN_PATH%

if "%ENABLE_OPTIMIZATIONS%"=="1" set NUITKA_CMD=%NUITKA_CMD% --lto=yes
if "%ONEFILE%"=="1" set NUITKA_CMD=%NUITKA_CMD% --onefile
if not "%WINDOWS_CONSOLE_MODE%"=="" set NUITKA_CMD=%NUITKA_CMD% --windows-console-mode=%WINDOWS_CONSOLE_MODE%

if exist "%DIST%" (
  echo [BuildNuitkaBAT] Limpando diretório dist... >> "%LOG%"
  rmdir /s /q "%DIST%" >> "%LOG%" 2>&1
)

echo [BuildNuitkaBAT] Executando Nuitka...
echo [BuildNuitkaBAT] %NUITKA_CMD% >> "%LOG%"
%NUITKA_CMD% >> "%LOG%" 2>&1
if errorlevel 1 goto :nuitka_fail

rem ---- 7) Valida artefatos críticos -------------------------------------------
if not exist "%DIST%\%OUTNAME%.exe" goto :artifact_fail
if not exist "%DIST%\QtWebEngineProcess.exe" goto :artifact_fail
if not exist "%DIST%\qt6webenginecore.dll" goto :artifact_fail
if not exist "%DIST%\qtwebengine_resources.pak" goto :artifact_fail
if not exist "%DIST%\v8_context_snapshot.bin" goto :artifact_fail
if not exist "%DIST%\_ctypes.pyd" goto :artifact_fail
if not exist "%DIST%\resources\chat\chat_view.html" goto :artifact_fail
if not exist "%DIST%\presentation\styles\app_styles.qss" goto :artifact_fail

rem ---- 8) Pós-build: garantir libffi no dist ----------------------------------
echo [BuildNuitkaBAT] Garantindo libffi no dist...
echo [BuildNuitkaBAT] Garantindo libffi no dist... >> "%LOG%"

set "BASE_PREFIX="
for /f "delims=" %%i in ('"%PYTHON_EXE%" -c "import sys; print(sys.base_prefix)" 2^>NUL') do set "BASE_PREFIX=%%i"
if "%BASE_PREFIX%"=="" (
  echo [BuildNuitkaBAT] Aviso: não consegui obter sys.base_prefix. >> "%LOG%"
) else (
  set "DLLS_DIR=%BASE_PREFIX%\DLLs"
  if exist "%DLLS_DIR%" (
    set "LIBFFI_SRC="
    for /f "delims=" %%F in ('dir /b "%DLLS_DIR%\libffi-*.dll" 2^>NUL') do (
      set "LIBFFI_SRC=%DLLS_DIR%\%%F"
      goto :copy_libffi
    )
  )
)

:copy_libffi
if not "%LIBFFI_SRC%"=="" (
  echo [BuildNuitkaBAT] Copiando "!LIBFFI_SRC!" -> "%DIST%" >> "%LOG%"
  copy /Y "!LIBFFI_SRC!" "%DIST%" >> "%LOG%" 2>&1
)

rem Verificação final libffi
set "FOUND_LIBFFI="
for /f "delims=" %%F in ('dir /b "%DIST%\libffi-*.dll" 2^>NUL') do set "FOUND_LIBFFI=%%F"
if "%FOUND_LIBFFI%"=="" (
  echo [BuildNuitkaBAT] ERRO: libffi-*.dll ausente no dist.
  echo [BuildNuitkaBAT] ERRO: libffi-*.dll ausente no dist. >> "%LOG%"
  exit /b 2
)

echo [BuildNuitkaBAT] SUCESSO! Artefatos em: "%DIST%"
echo [BuildNuitkaBAT] SUCESSO! Artefatos em: "%DIST%" >> "%LOG%"
exit /b 0

rem =============================== TRATAMENTO DE ERROS =========================
:pip_fail
echo [BuildNuitkaBAT] ERRO durante pip install (veja "%LOG%").
exit /b 10

:nuitka_fail
echo [BuildNuitkaBAT] ERRO durante a compilacao Nuitka (veja "%LOG%").
exit /b 11

:artifact_fail
echo [BuildNuitkaBAT] ERRO: artefato essencial ausente no dist (veja "%LOG%").
exit /b 12
