@echo off
setlocal
call "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64


REM === 3) Caminhos e arquivos ===
set SRC=launcher.cpp
set RESRC=launcher.rc
set RESOBJ=launcher.res
set OUT=ChatbotAI_launcher.exe

echo [INFO] Iniciando build do launcher...
REM === 4) Compilar recursos (icone) ===
if not exist resources\launcher.ico (
  echo [AVISO] resources\launcher.ico nao encontrado. O arquivo de recursos pode falhar.
)

echo [INFO] Compilando recursos...

rc /nologo /fo %RESOBJ% %RESRC%
if errorlevel 1 pause exit /b 1

REM === 5) Compilar C++ (otimizado) ===
REM /EHsc: excecoes C++; /O2: otimizacao; /GL + /LTCG: LTO; /DUNICODE: wide; /MT: runtime estatico (exe mais autonomo)
cl /nologo /std:c++20 /utf-8 /W4 /EHsc /O2 /GL /DUNICODE /D_UNICODE /MT %SRC% %RESOBJ% ^
   /Fe:%OUT% ^
   /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup /LTCG /DYNAMICBASE /NXCOMPAT ^
   Gdiplus.lib User32.lib Gdi32.lib UxTheme.lib Dwmapi.lib Shlwapi.lib Advapi32.lib Shell32.lib

if errorlevel 1 pause exit /b 1

echo [OK] Build finalizado: %OUT%

REM === 6) (Opcional) Assinatura de codigo ===
REM set CERT_THUMBPRINT=SEU_POLEGAR_DA_CERT
REM signtool sign /sha1 %CERT_THUMBPRINT% /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 "%OUT%"

pause
endlocal
