# Licencias de terceros

El **código fuente** de este repositorio se publica bajo licencia **MIT** (ver [LICENSE](LICENSE)).

Los `.exe` que se publican en *Releases* son programas compilados con PyInstaller y **incluyen**:

| Componente | Licencia | Texto / origen |
|---|---|---|
| **PyQt6** 6.12.1 | **GPL v3** (o licencia comercial de Riverbank) | [licenses/PyQt6-GPL-3.0.txt](licenses/PyQt6-GPL-3.0.txt) · <https://www.riverbankcomputing.com/software/pyqt/> |
| **Qt 6** 6.12 (Qt6Core, Qt6Gui, Qt6Widgets y el plugin de ventanas de Windows) | LGPL v3 | [licenses/Qt6-LGPL-3.0.txt](licenses/Qt6-LGPL-3.0.txt) · <https://www.qt.io/> |
| **Python** 3.14 (intérprete y biblioteca estándar) | PSF License | <https://docs.python.org/3/license.html> |
| **PyInstaller** (cargador del .exe) | GPL v2 con excepción para el cargador (permite distribuir el .exe bajo cualquier licencia) | <https://pyinstaller.org/> |
| Fotografía de la cucaracha | **CC0** (dominio público) — Alex Wild / Insects Unlocked, Univ. de Texas en Austin, vía Wikimedia Commons | <https://commons.wikimedia.org/> |

## Qué implica para el .exe
Como el programa compilado enlaza con PyQt6 (GPL v3), **el binario en su conjunto se distribuye bajo los términos de la GPL v3**. El código fuente completo y correspondiente de cada versión es este repositorio (etiqueta `vX.Y.Z` de cada release), y se puede recompilar con `herramientas\crear_exe.bat`. Las bibliotecas de Qt (LGPL) viajan como DLL propias dentro del .exe y se pueden reemplazar recompilando.

Si se quisiera distribuir sin los términos de la GPL, habría que cambiar PyQt6 por PySide6 (Qt for Python, LGPL) o comprar una licencia comercial de PyQt.

## Lo que NO se incluye
Las fotos de arañas que el autor usa en su copia personal provienen de bancos de imágenes sin licencia de redistribución: no están en este repositorio ni en los .exe publicados.
