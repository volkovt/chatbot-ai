@echo off
setlocal enabledelayedexpansion

rem -----------------------------
rem Config
rem -----------------------------
set PYTHON=py -3.12
set OUT_DIR=dist\release
set SPEC_FILE=pyinstaller_bundle.spec
set INNO_ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

echo [1/6] Clean previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist installer_out rmdir /s /q installer_out
mkdir dist

echo [2/6] Ensure dependencies (PyInstaller + project reqs)...
%PYTHON% -m pip install --upgrade pip >nul
if exist requirements.txt (
  %PYTHON% -m pip install -r requirements.txt
  if errorlevel 1 ( echo ERROR: pip requirements failed. & exit /b 1 )
)
%PYTHON% -m pip install pyinstaller >nul
if errorlevel 1 ( echo ERROR: installing PyInstaller failed. & exit /b 1 )

echo [3/6] Building both executables with PyInstaller (one-dir)...
%PYTHON% -m PyInstaller --noconfirm --clean %SPEC_FILE% --distpath "%OUT_DIR%" --workpath build --log-level WARN
if errorlevel 1 ( echo ERROR: PyInstaller build failed. & exit /b 1 )

if not exist "%OUT_DIR%\launcher.exe" (
  echo ERROR: launcher.exe not found in %OUT_DIR%.
  exit /b 1
)
if not exist "%OUT_DIR%\ChatbotAI.exe" (
  echo ERROR: ChatbotAI.exe not found in %OUT_DIR%.
  exit /b 1
)

echo [4/6] (Optional) Code signing...
rem Configure these env vars if you want signing:
rem set SIGNTOOL="C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"
rem set CERT_PATH=C:\path\to\cert.pfx
rem set CERT_PASS=your_password
if defined SIGNTOOL if defined CERT_PATH if defined CERT_PASS (
  %SIGNTOOL% sign /fd sha256 /f "%CERT_PATH%" /p "%CERT_PASS%" /tr http://timestamp.digicert.com /td sha256 "%OUT_DIR%\launcher.exe"
  %SIGNTOOL% sign /fd sha256 /f "%CERT_PATH%" /p "%CERT_PASS%" /tr http://timestamp.digicert.com /td sha256 "%OUT_DIR%\ChatbotAI.exe"
)

echo [5/6] Building installer with Inno Setup...
if exist %INNO_ISCC% (
  %INNO_ISCC% inno_installer.iss
) else (
  echo WARN: ISCC.exe not found. Skipping installer build. Install Inno Setup 6 to generate the installer EXE.
)

echo [6/6] Done.
echo Output folder: %OUT_DIR%
if exist installer_out dir /b installer_out
exit /b 0
