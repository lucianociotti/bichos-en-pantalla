# -*- coding: utf-8 -*-
"""
Arma el paquete MSIX de "Bichos en pantalla" para la Microsoft Store (Microsoft lo firma gratis al publicarlo).

  python herramientas\\crear_msix.py                 compila el .exe de tienda, logos, capturas y el .msix
  python herramientas\\crear_msix.py --sin-compilar  reutiliza dist\\tienda\\exe\\BichosPantalla.exe
  python herramientas\\crear_msix.py --con-aranas    incluye las arañas con foto (SOLO si tenés licencia)

Salida en dist\\tienda\\ :
  BichosPantalla_<version>_x64.msix   el paquete (se sube a Partner Center, o se prueba con el modo desarrollador)
  ficha\\                              logos y capturas para la ficha de la Store
La identidad (nombre/publisher) sale de herramientas\\msix\\identidad.txt; ver herramientas\\msix\\LEEME_STORE.md.
Requiere el Windows SDK (makeappx y makepri), PyQt6, Pillow y PyInstaller.
"""
import argparse
import glob
import hashlib
import math
import os
import re
import shutil
import subprocess
import sys
from xml.sax.saxutils import escape

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, ".."))
PLANTILLA = os.path.join(AQUI, "msix", "AppxManifest.plantilla.xml")
IDENTIDAD_LOCAL = os.path.join(AQUI, "msix", "identidad.local.txt")   # real, fuera de git
IDENTIDAD = IDENTIDAD_LOCAL if os.path.isfile(IDENTIDAD_LOCAL) else os.path.join(AQUI, "msix", "identidad.txt")
SALIDA = os.path.join(RAIZ, "dist", "tienda")
TRABAJO = os.path.join(RAIZ, "build", "msix")
LAYOUT = os.path.join(TRABAJO, "layout")
EXE_TIENDA = os.path.join(SALIDA, "exe", "BichosPantalla.exe")
FICHA = os.path.join(SALIDA, "ficha")

COLOR_PLACA = (232, 225, 211, 255)   # fondo claro de los logos: la cucaracha oscura se ve en tema claro y oscuro
ESCALAS = (100, 125, 150, 200, 400)


def fallar(msg):
    print("ERROR:", msg)
    sys.exit(1)


def herramienta_sdk(nombre):
    cand = []
    for p in glob.glob(r"C:\Program Files (x86)\Windows Kits\10\bin\*\x64\%s" % nombre):
        m = re.search(r"\\(10\.0\.[\d.]+)\\", p)
        if m:
            cand.append((tuple(int(x) for x in m.group(1).split(".")), p))
    if not cand:
        fallar("no encuentro %s: instalá el Windows SDK (componente 'Windows SDK Signing Tools / MSIX')." % nombre)
    return sorted(cand)[-1][1]


def correr(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print(r.stdout[-2500:], r.stderr[-2500:])
        fallar("falló: %s" % " ".join(str(c) for c in cmd[:3]))
    return r.stdout


def leer_identidad():
    datos = {}
    with open(IDENTIDAD, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                datos[k.strip().upper()] = v.strip()
    for k in ("NOMBRE", "PUBLISHER", "EDITOR", "VERSION"):
        if not datos.get(k):
            fallar("falta %s en %s" % (k, IDENTIDAD))
    if not re.fullmatch(r"[A-Za-z0-9.\-]{3,50}", datos["NOMBRE"]):
        fallar("NOMBRE inválido (3-50 caracteres: letras, números, punto y guion)")
    if not re.fullmatch(r"\d+\.\d+\.\d+\.0", datos["VERSION"]):
        fallar("VERSION debe tener 4 números y terminar en .0 (la Store reserva el último), ej. 1.0.0.0")
    datos["PRUEBA"] = datos["NOMBRE"].endswith(".Prueba")
    return datos


def compilar_exe(con_aranas):
    env = dict(os.environ)
    env["BICHOS_SOLO_CC0"] = "0" if con_aranas else "1"
    dist = os.path.join(SALIDA, "exe")
    print("[1/5] compilando el .exe de tienda (%s)..." % ("con arañas con foto" if con_aranas else "solo fotos CC0"))
    correr([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", dist,
            "--workpath", os.path.join(RAIZ, "build", "tienda"), os.path.join(AQUI, "BichosPantalla.spec")],
           env=env, cwd=RAIZ)
    shutil.rmtree(os.path.join(RAIZ, "build", "tienda"), ignore_errors=True)


# ---------------------------------------------------------------- logos y capturas (usan el propio render del programa)
def iniciar_qt(con_aranas):
    sys.path.insert(0, RAIZ)
    from PyQt6.QtGui import QGuiApplication
    import bichos
    app = QGuiApplication(sys.argv)
    bichos.load_sprites()
    if not con_aranas:
        bichos.SPRITES["arana"].clear()   # igual que el .exe de tienda: la araña se dibuja vectorial
    return app, bichos


def cucaracha_rgba(B, esc=2.5):
    from PIL import Image
    from PyQt6.QtGui import QImage, QPainter
    c = B.Creature(B.ROACH, esc, (0, 0), (0, -1e5), 0, debug_speed=0.5 * B.ROACH.vmax)
    for _ in range(80):
        c.update(1 / 60.0)
    side = int(2 * B.ROACH.R * esc)
    img = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    sh = QImage(int(side * B.SHADOW_K) + 1, int(side * B.SHADOW_K) + 1, QImage.Format.Format_ARGB32_Premultiplied)
    c.paint(p, c.x - side / 2, c.y - side / 2, side, sh)
    p.end()
    tmp = os.path.join(TRABAJO, "_cuca.png")
    img.save(tmp)
    im = Image.open(tmp).convert("RGBA")
    im = im.crop(im.getchannel("A").point(lambda v: 255 if v > 30 else 0).getbbox())
    os.remove(tmp)
    return im


def placa_con_cucaracha(cuca, w, h, redondeo, relleno):
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=int(min(w, h) * redondeo), fill=COLOR_PLACA)
    k = relleno * min(w, h) / max(cuca.size)
    ch = cuca.resize((max(1, int(cuca.width * k)), max(1, int(cuca.height * k))), Image.LANCZOS)
    im.paste(ch, ((w - ch.width) // 2, (h - ch.height) // 2), ch)
    return im


def hacer_logos(B, assets):
    from PIL import Image
    os.makedirs(assets, exist_ok=True)
    os.makedirs(FICHA, exist_ok=True)
    cuca = cucaracha_rgba(B)
    cuadrado = placa_con_cucaracha(cuca, 1024, 1024, 0.2, 0.80)
    ancho = placa_con_cucaracha(cuca, 1240, 600, 0.0, 0.84)

    def redim(im, w, h):
        return im.resize((w, h), Image.LANCZOS)

    for nombre, base in (("Square44x44Logo", 44), ("Square150x150Logo", 150), ("StoreLogo", 50)):
        for e in ESCALAS:
            lado = int(base * e / 100 + 0.5)
            redim(cuadrado, lado, lado).save(os.path.join(assets, "%s.scale-%d.png" % (nombre, e)))
    for e in ESCALAS:
        redim(ancho, int(310 * e / 100 + 0.5), int(150 * e / 100 + 0.5)).save(
            os.path.join(assets, "Wide310x150Logo.scale-%d.png" % e))
    for t in (16, 24, 32, 48, 256):
        for suf in ("", "_altform-unplated"):
            redim(cuadrado, t, t).save(os.path.join(assets, "Square44x44Logo.targetsize-%d%s.png" % (t, suf)))
    redim(cuadrado, 300, 300).save(os.path.join(FICHA, "logo_300x300.png"))
    redim(cuadrado, 1080, 1080).save(os.path.join(FICHA, "logo_1080x1080.png"))


def hacer_capturas(B):
    """Escenas con el propio render del programa sobre un fondo neutro (NO capturan tu pantalla)."""
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QRadialGradient

    def fondo(c1, c2, brillo):
        img = QImage(1920, 1080, QImage.Format.Format_ARGB32_Premultiplied)
        p = QPainter(img)
        g = QLinearGradient(0, 0, 1920, 1080)
        g.setColorAt(0, QColor(*c1))
        g.setColorAt(1, QColor(*c2))
        p.fillRect(0, 0, 1920, 1080, g)
        for cx, cy, r in ((420, 300, 620), (1500, 820, 700)):
            rg = QRadialGradient(cx, cy, r)
            rg.setColorAt(0, QColor(*brillo, 70))
            rg.setColorAt(1, QColor(*brillo, 0))
            p.fillRect(QRectF(0, 0, 1920, 1080), rg)
        return img, p

    def bicho(p, spec, variante, esc, cx, cy, rumbo):
        side = int(2 * 185 * esc)
        far = (math.cos(rumbo) * 1e5, math.sin(rumbo) * 1e5)
        c = B.Creature(spec, esc, (0, 0), far, variante, debug_speed=0.55 * spec.vmax * esc)
        for _ in range(110):
            c.update(1 / 60.0)
        sh = QImage(int(side * B.SHADOW_K) + 1, int(side * B.SHADOW_K) + 1, QImage.Format.Format_ARGB32_Premultiplied)
        p.save()
        p.translate(cx - side / 2, cy - side / 2)
        c.paint(p, c.x - side / 2, c.y - side / 2, side, sh)
        p.restore()

    escenas = [
        ("captura_1_cucaracha", (176, 198, 222), (222, 232, 242), (255, 255, 255), [(B.ROACH, 1, 1.5, 1130, 560, 0.5)]),
        ("captura_2_arana", (34, 42, 58), (78, 96, 122), (150, 175, 215), [(B.SPIDER, 0, 1.7, 820, 600, -0.4)]),
        ("captura_3_dos_bichos", (214, 196, 170), (240, 226, 204), (255, 240, 215),
         [(B.ROACH, 0, 1.0, 560, 400, 2.6), (B.SPIDER, 1, 1.1, 1340, 720, 0.2)]),
    ]
    for nombre, c1, c2, br, bichos_ in escenas:
        img, p = fondo(c1, c2, br)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for spec, var, esc, cx, cy, rumbo in bichos_:
            bicho(p, spec, var, esc, cx, cy, rumbo)
        p.end()
        img.save(os.path.join(FICHA, nombre + ".png"))


# ---------------------------------------------------------------- paquete
def armar_paquete(ident, assets):
    makepri = herramienta_sdk("makepri.exe")
    makeappx = herramienta_sdk("makeappx.exe")
    shutil.rmtree(LAYOUT, ignore_errors=True)
    os.makedirs(os.path.join(LAYOUT, "Assets"))
    shutil.copy2(EXE_TIENDA, LAYOUT)
    for f in os.listdir(assets):
        shutil.copy2(os.path.join(assets, f), os.path.join(LAYOUT, "Assets", f))
    with open(PLANTILLA, encoding="utf-8") as f:
        xml = f.read()
    for k, v in (("NOMBRE", ident["NOMBRE"]), ("PUBLISHER", ident["PUBLISHER"]),
                 ("EDITOR", ident["EDITOR"]), ("VERSION", ident["VERSION"])):
        xml = xml.replace("{{%s}}" % k, escape(v, {'"': "&quot;"}))
    manifiesto = os.path.join(LAYOUT, "AppxManifest.xml")
    with open(manifiesto, "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)
    cfg = os.path.join(TRABAJO, "priconfig.xml")
    correr([makepri, "createconfig", "/cf", cfg, "/dq", "es", "/pv", "10.0.0", "/o"])
    # Sin "autoResourcePackages": si no, makepri parte los recursos en resources.scale-*.pri (eso es para bundles)
    with open(cfg, "rb") as f:
        crudo = f.read()
    enc = "utf-16" if crudo[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    txt = re.sub(r"<packaging>.*?</packaging>", "", crudo.decode(enc), flags=re.S)
    with open(cfg, "wb") as f:
        f.write(txt.encode(enc))
    correr([makepri, "new", "/pr", LAYOUT, "/cf", cfg, "/mn", manifiesto,
            "/of", os.path.join(LAYOUT, "resources.pri"), "/o"])
    salida = os.path.join(SALIDA, "BichosPantalla_%s_x64.msix" % ident["VERSION"])
    if os.path.exists(salida):
        os.remove(salida)
    correr([makeappx, "pack", "/d", LAYOUT, "/p", salida, "/o"])
    return salida


def main():
    ap = argparse.ArgumentParser(description="Arma el MSIX de Bichos en pantalla")
    ap.add_argument("--sin-compilar", action="store_true", help="reutiliza dist\\tienda\\exe\\BichosPantalla.exe")
    ap.add_argument("--con-aranas", action="store_true", help="incluye las arañas con foto (solo con licencia)")
    args = ap.parse_args()

    ident = leer_identidad()
    os.makedirs(SALIDA, exist_ok=True)
    os.makedirs(TRABAJO, exist_ok=True)
    if args.sin_compilar and os.path.isfile(EXE_TIENDA):
        print("[1/5] reutilizando", EXE_TIENDA)
    else:
        compilar_exe(args.con_aranas)
    print("[2/5] logos y capturas...")
    app, B = iniciar_qt(args.con_aranas)
    assets = os.path.join(TRABAJO, "assets")
    shutil.rmtree(assets, ignore_errors=True)
    hacer_logos(B, assets)
    print("[3/5] capturas de la ficha...")
    hacer_capturas(B)
    print("[4/5] armando el paquete...")
    msix = armar_paquete(ident, assets)
    print("[5/5] listo")
    h = hashlib.sha256(open(msix, "rb").read()).hexdigest().upper()
    print("  paquete :", msix, "(%.1f MB)" % (os.path.getsize(msix) / 1048576))
    print("  SHA256  :", h)
    print("  ficha   :", FICHA)
    if ident["PRUEBA"]:
        print("  OJO: identidad de PRUEBA -> sirve para probar en tu PC, NO para subir a la Store (ver herramientas\\msix\\identidad.txt).")


if __name__ == "__main__":
    main()
