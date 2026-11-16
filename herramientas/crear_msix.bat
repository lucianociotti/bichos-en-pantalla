@echo off
rem Arma dist\tienda\BichosPantalla_<version>_x64.msix (para la Microsoft Store) + logos y capturas de la ficha.
rem Opciones: --sin-compilar (reusa el .exe de tienda)  --con-aranas (solo si tenes licencia de las fotos)
cd /d "%~dp0.."
python herramientas\crear_msix.py %*
pause
