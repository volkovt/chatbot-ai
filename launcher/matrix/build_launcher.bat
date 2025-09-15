@echo off
setlocal EnableExtensions EnableDelayedExpansion
call "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64

@echo off
setlocal
echo [RC] MatrixLauncher.rc
rc /nologo /fo MatrixLauncher.res MatrixLauncher.rc || goto :err

echo [CL] MatrixLauncher.c -> .obj (C++)
cl /nologo /c /TP /W4 /EHsc /O2 /GL /DUNICODE /D_UNICODE MatrixLauncher.c || goto :err

echo [LINK] .obj + .res
link /NOLOGO /LTCG MatrixLauncher.obj MatrixLauncher.res ^
     gdiplus.lib shlwapi.lib ole32.lib comctl32.lib user32.lib gdi32.lib shell32.lib uxtheme.lib dwmapi.lib || goto :err

echo [OK] Build concluido.
exit /b 0
:err
echo [FAIL] Build error.
exit /b 1