# -*- coding: utf-8 -*-
"""
Revisión de seguridad rápida del .exe compilado (ver docs/GUIA.md, sección Seguridad).

  python herramientas\\auditoria\\auditar_exe.py [ruta\\al\\BichosPantalla.exe]

Comprueba: que no vayan módulos de red/procesos/registro/criptografía, que el manifiesto no pida
administrador, que no haya DLL de red/cripto propias, que no estén los sprites de arañas de banco de
imágenes y que el código no contenga datos de quien compiló. Sale con código 1 si algo no cuadra.
Requiere: pip install pefile pyinstaller
"""
import hashlib
import marshal
import os
import re
import sys
import types

import pefile
from PyInstaller.archive.readers import CArchiveReader

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EXE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, "dist", "tienda", "exe", "BichosPantalla.exe")
USUARIO = os.path.basename(os.path.expanduser("~"))

# Módulos que el programa NO debe llevar (red, correo, ejecutar programas, registro, serialización insegura...)
RIESGO = {"socket", "_socket", "ssl", "_ssl", "http", "urllib", "email", "smtplib", "ftplib", "netrc", "xmlrpc",
          "subprocess", "pickle", "winreg", "hashlib", "_hashlib", "select", "selectors", "xml", "tarfile", "bz2",
          "lzma", "sqlite3", "asyncio", "multiprocessing", "tkinter", "numpy", "PIL", "scipy", "devtools", "unittest"}
DLL_RIESGO = ("ssl", "crypto", "network", "svg", "pdf", "opengl", "d3d", "_socket", "_hashlib", "_ssl", "sqlite", "lzma", "bz2")
NOMBRES_RIESGO = {"socket", "subprocess", "winreg", "pickle", "eval", "exec", "system", "popen", "grabWindow",
                  "startfile", "urlopen"}
# Nombres sensibles que SÍ aparecen en bichos.py y son legítimos (si aparece otro, revisar):
ESPERADOS = {
    "exec": "app.exec(), el bucle de eventos de Qt",
    "startfile": "menú 'Ver registro (log)': abre el log con tu editor de texto, solo si el usuario lo elige",
    "winreg": "'Iniciar con Windows', solo en desarrollo: el .exe no lleva winreg y ese menú no existe",
}
problemas = []


def marca(ok, texto):
    print("  [%s] %s" % ("OK" if ok else "!!", texto))
    if not ok:
        problemas.append(texto)


if not os.path.isfile(EXE):
    sys.exit("No encuentro el .exe: %s" % EXE)
print("== %s" % EXE)
with open(EXE, "rb") as f:
    datos = f.read()
print("  tamaño: %.1f MB   SHA256: %s" % (len(datos) / 1048576, hashlib.sha256(datos).hexdigest().upper()))

print("\n1) Permisos (manifiesto)")
pe = pefile.PE(EXE)
man = ""
for t in pe.DIRECTORY_ENTRY_RESOURCE.entries:
    if t.id == 24:  # RT_MANIFEST
        for n in t.directory.entries:
            for lang in n.directory.entries:
                d = lang.data.struct
                man = pe.get_data(d.OffsetToData, d.Size).decode("utf-8", "replace")
m = re.search(r'requestedExecutionLevel[^>]*level="([^"]+)"', man)
marca(bool(m) and m.group(1) == "asInvoker", "nivel de ejecución: %s (debe ser asInvoker: sin UAC)" % (m.group(1) if m else "sin manifiesto"))

print("\n2) Contenido empaquetado")
ar = CArchiveReader(EXE)
pyz = ar.open_embedded_archive("PYZ.pyz")
mods = sorted(pyz.toc.keys() if hasattr(pyz.toc, "keys") else [t[0] for t in pyz.toc])
malos = [x for x in mods if x.split(".")[0] in RIESGO]
marca(not malos, "módulos de riesgo dentro del .exe: %s" % (malos or "ninguno"))
dlls = [n for n in ar.toc if n.lower().endswith((".dll", ".pyd")) and not n.startswith("api-ms")]
dll_malas = [n for n in dlls if any(k in n.lower() for k in DLL_RIESGO)]
marca(not dll_malas, "DLL/PYD de red, cripto, SVG, OpenGL...: %s" % (dll_malas or "ninguna"))
sprites = [n for n in ar.toc if n.replace("\\", "/").startswith("sprites/")]
arana = [n for n in sprites if "arana_" in n]
marca(not arana, "sprites de arañas con foto: %s (la variante pública no debe llevarlos)" % (arana or "ninguno"))

print("\n3) Datos de quien compiló y llamadas sensibles en el código del programa")
co = ar.extract("bichos")
co = marshal.loads(co) if isinstance(co, bytes) else co
textos, nombres = [co.co_filename], set()


def recorrer(c):
    textos.extend([k for k in c.co_consts if isinstance(k, str)])
    nombres.update(c.co_names)
    for k in c.co_consts:
        if isinstance(k, types.CodeType):
            recorrer(k)


recorrer(co)
buscar = [USUARIO.lower(), "c:\\users\\" + USUARIO.lower(), "password", "token", "secret", "api_key"]
con_datos = sorted({t[:80] for t in textos for b in buscar if b and b in t.lower()})
marca(not con_datos, "textos con usuario/credenciales: %s" % (con_datos or "ninguno"))
usados = sorted(nombres & NOMBRES_RIESGO)
inesperados = [n for n in usados if n not in ESPERADOS]
marca(not inesperados, "nombres sensibles inesperados en el código: %s" % (inesperados or "ninguno"))
for n in usados:
    if n in ESPERADOS:
        print("  [i] aparece '%s': %s" % (n, ESPERADOS[n]))

print("\n%s" % ("TODO EN ORDEN" if not problemas else "REVISAR: %d problema(s)" % len(problemas)))
sys.exit(1 if problemas else 0)
