@echo off
rem Compila dist\BichosPantalla.exe (un solo archivo, sin consola, con las fotos adentro).
rem Usa herramientas\BichosPantalla.spec, que deja afuera todo lo que el programa no usa.
rem Requiere: Python con PyQt6 y PyInstaller (pip install PyQt6 pyinstaller).
cd /d "%~dp0.."
python -m PyInstaller --noconfirm --clean --distpath "%CD%\dist" --workpath "%CD%\build" "%CD%\herramientas\BichosPantalla.spec"
echo.
echo Listo: %CD%\dist\BichosPantalla.exe
rmdir /s /q "%CD%\build" 2>nul
pause
