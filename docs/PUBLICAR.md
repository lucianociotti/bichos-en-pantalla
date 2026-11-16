# Cómo sacar una versión nueva

Pasos para publicar, por ejemplo, la 1.1.0 (sonidos, interacciones...). Los comandos son de PowerShell, desde la raíz del repo.

## 1. Desarrollar y probar
- `python bichos.py --ya` para probar en vivo; `python bichos.py --png prueba.png` genera una hoja de prueba sin abrir ventanas.
- Si la novedad suma código que toca el sistema (sonido, archivos, red...), **repetir la revisión de seguridad** (paso 4) y actualizar la sección *Seguridad* de [GUIA.md](GUIA.md).
- Sonidos: usar `winsound` (biblioteca estándar, WAV). Qt Multimedia agrega ffmpeg y mucho peso y superficie de ataque. Los WAV van en una carpeta nueva (`sonidos/`) que hay que agregar a `datas` en `herramientas\BichosPantalla.spec`.

## 2. Subir la versión
Cambiar el número en **tres** lugares:
- `herramientas\version_info.txt` (`filevers`, `prodvers` y `FileVersion`/`ProductVersion`),
- `herramientas\msix\identidad.local.txt` → `VERSION=1.1.0.0` (para la Store el último número queda siempre en `0`),
- `CHANGELOG.md` (mover lo de "Sin publicar" a la versión nueva, con fecha).

## 3. Compilar la versión pública
```powershell
python herramientas\crear_msix.py
```
Deja en `dist\tienda\`: `exe\BichosPantalla.exe` (para GitHub), `BichosPantalla_<versión>_x64.msix` (para la Store) y las imágenes de la ficha. Es la variante **sin fotos de arañas de banco de imágenes**; en un clon limpio del repo ya es así porque esos sprites no se versionan.

## 4. Revisar el .exe
```powershell
pip install pefile pyinstaller
python herramientas\auditoria\auditar_exe.py            # módulos de riesgo, manifiesto, datos personales
powershell -File herramientas\auditoria\probar_exe.ps1 -Exe dist\tienda\exe\BichosPantalla.exe   # arranca aislado, mira red y ventanas
```
El resultado esperado: sin módulos de red/procesos/registro, `asInvoker`, 0 conexiones y ningún diálogo de error. También conviene pasar Windows Defender y correr `pip install pip-audit && python -m pip_audit`.

## 5. Publicar en GitHub
```powershell
git add -A; git commit -m "v1.1.0: <resumen>"
git tag v1.1.0; git push; git push --tags
$h = (Get-FileHash dist\tienda\exe\BichosPantalla.exe).Hash
gh release create v1.1.0 dist\tienda\exe\BichosPantalla.exe --title "v1.1.0" --notes "<novedades>`n`nSHA256: $h"
```

## 6. Publicar en la Microsoft Store
Partner Center → la app → *Actualizar* (nuevo envío) → *Paquetes*: subir el `.msix` (con versión mayor a la anterior) → completar *Novedades de esta versión* en la ficha → *Enviar para certificación*. La publicación está en modo manual: al aprobarse, hay que apretar *Publicar ahora*.

## Notas
- La identidad de la Store (nombre, publisher) vive en `herramientas\msix\identidad.local.txt`, que **no se versiona**.
- El .exe de GitHub no tiene firma digital: SmartScreen avisa hasta que gane reputación o se firme (SignPath es gratis para proyectos open source).
