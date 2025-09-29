@echo off
setlocal
pushd "%~dp0"

rem === 1) MSVC toolset (x64) ===
call "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64

rem === 2) Fontes e saida ===
set "SRC=itau_loader.cpp"
set "OUT=itau_loader.exe"

echo [INFO] Compilando e linkando (sem Qt)...
cl /nologo /std:c++20 /utf-8 /W4 /EHsc /O2 /GL /DUNICODE /D_UNICODE /MT ^
  "%SRC%" ^
  /Fe:"%OUT%" ^
  /link /SUBSYSTEM:WINDOWS /ENTRY:wWinMainCRTStartup /LTCG /DYNAMICBASE /NXCOMPAT ^
  Gdiplus.lib User32.lib Gdi32.lib UxTheme.lib Dwmapi.lib Shlwapi.lib Advapi32.lib Shell32.lib
if errorlevel 1 (
  echo [ERRO] Falha no build.
  pause
  popd
  exit /b 1
)

echo [OK] Build finalizado: %OUT%
pause
popd
endlocal