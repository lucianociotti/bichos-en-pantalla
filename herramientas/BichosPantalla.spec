# -*- mode: python ; coding: utf-8 -*-
# Receta de PyInstaller para BichosPantalla.exe, pensada para llevar SOLO lo que el programa usa
# (menos código dentro del .exe = menos superficie de ataque y menos falsos positivos de antivirus).
# Se usa con herramientas\crear_exe.bat

import os

RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))

# Módulos de Python que el programa no usa: red, correo, HTTP, FTP, criptografía, ejecución de otros
# programas, compresión, XML, pruebas... y las herramientas de desarrollo (capturas de pantalla).
EXCLUIR = [
    "tkinter", "numpy", "scipy", "PIL", "devtools", "winreg",
    "ssl", "_ssl", "hashlib", "_hashlib", "socket", "_socket", "select", "selectors",
    "http", "urllib", "email", "ftplib", "smtplib", "netrc", "xml", "xmlrpc",
    # (zipfile/shutil/tempfile NO se excluyen: los necesita el propio arranque de PyInstaller)
    "subprocess", "pickle", "tarfile", "bz2", "lzma", "_bz2", "_lzma", "zstd", "_zstd",
    "unittest", "pydoc", "doctest", "sqlite3", "asyncio", "multiprocessing", "concurrent",
]

a = Analysis(
    [os.path.join(RAIZ, "bichos.py")],
    pathex=[RAIZ],
    binaries=[],
    datas=[(os.path.join(RAIZ, "sprites"), "sprites")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUIR,
    noarchive=False,
)

# Qt: se queda solo con lo necesario para abrir ventanas transparentes y dibujar:
#   Qt6Core, Qt6Gui, Qt6Widgets, plugin de plataforma "windows" y estilo de Windows.
# Se quita: red (Qt6Network), SVG, lectores de imágenes (el PNG ya viene dentro de Qt6Gui),
# OpenGL por software, plugins de entrada táctil y todas las traducciones.
QUITAR = ("qt6network", "qt6svg", "qt6pdf", "opengl32sw", "d3dcompiler",
          "\\imageformats\\", "\\iconengines\\", "\\generic\\", "\\platforminputcontexts\\",
          "\\networkinformation\\", "\\tls\\", "qminimal", "qoffscreen", "qdirect2d", "\\translations\\")


def _se_queda(destino):
    d = destino.lower().replace("/", "\\")
    return not any(q in d for q in QUITAR)


a.binaries = [b for b in a.binaries if _se_queda(b[0])]
a.datas = [d for d in a.datas if _se_queda(d[0])]

# Variante para repartir públicamente (Microsoft Store): BICHOS_SOLO_CC0=1 deja afuera los sprites de
# arañas, que salen de fotos de banco de imágenes sin licencia de redistribución (la araña se dibuja
# vectorial). La usa herramientas\crear_msix.py; el .exe de uso personal los lleva.
if os.environ.get("BICHOS_SOLO_CC0") == "1":
    a.datas = [d for d in a.datas if not os.path.basename(d[0]).startswith("arana_")]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BichosPantalla",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                       # sin UPX: empaquetar con UPX dispara antivirus
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True,  # sin ventana de error con rutas del equipo (los errores van al log)
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(RAIZ, "bichos.ico"),
    version=os.path.join(SPECPATH, "version_info.txt"),
)
