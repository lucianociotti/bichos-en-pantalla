# -*- coding: utf-8 -*-
"""
Bichos en pantalla
==================
De vez en cuando (al azar) una cucaracha o una araña cruza el escritorio.

- Se dibujan con vectores (sin imágenes): cuerpo con relieve y brillo, sombra
  suave sobre lo que haya debajo, patas articuladas con cinemática inversa y
  marcha en trípode (cucaracha) / tetrápodo alternado (araña).
- Corren a ráfagas, se frenan, mueven antenas/palpos y se escapan del mouse.
- Ventana transparente, siempre arriba y "fantasma": los clics pasan de largo.
- Vive en la bandeja del sistema (junto al reloj): frecuencia, tipo, tamaño.

Uso:
    pythonw bichos.py            -> se queda en la bandeja
    pythonw bichos.py --ya       -> además suelta uno enseguida
    (las pruebas y capturas están en devtools.py, que NO se empaqueta en el .exe)

Alcance (lo único que hace este programa):
    - dibuja ventanas transparentes con un bicho y las mueve por el escritorio
    - lee la posición del mouse (solo para que el bicho se asuste; no se guarda ni se registra)
    - guarda sus ajustes y un log técnico en su propia carpeta
    No usa red, no ejecuta otros programas, no lee archivos ajenos, no captura pantalla ni teclado,
    no toca el registro de Windows (en el .exe) y no pide permisos de administrador.
"""
import atexit
import faulthandler
import logging
import math
import os
import random
import sys
import threading
import time
import traceback

from PyQt6.QtCore import (QElapsedTimer, QLockFile, QPoint, QPointF, QRectF, QSettings, Qt, QTimer, QtMsgType,
                          qInstallMessageHandler)
from PyQt6.QtGui import (QAction, QActionGroup, QColor, QCursor, QGuiApplication, QIcon,
                         QImage, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient)
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
TAU = math.tau
FROZEN = getattr(sys, "frozen", False)           # True cuando corre como .exe (PyInstaller)
RES_DIR = getattr(sys, "_MEIPASS", HERE)         # recursos empaquetados dentro del .exe (sprites)
TEMP_DIR = os.environ.get("TEMP") or os.environ.get("TMP") or HERE   # temporal del usuario (no compartida)
DATA_DIR = HERE                                  # donde se guardan log y ajustes
AUTOSTART = not FROZEN                           # el .exe no toca el registro de Windows (sin "Iniciar con Windows")
if FROZEN:
    # el .exe puede estar en un pendrive o en una carpeta sin permiso de escritura: ajustes y logs
    # van a %LOCALAPPDATA%\BichosPantalla y no quedan ensuciando junto al .exe
    try:
        DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or TEMP_DIR, "BichosPantalla")
        os.makedirs(DATA_DIR, exist_ok=True)
    except OSError:
        DATA_DIR = os.path.join(TEMP_DIR, "BichosPantalla")
        os.makedirs(DATA_DIR, exist_ok=True)


# ----------------------------------------------------------------------------
# registro (logs): todo lo importante queda en bichos.log, al lado del programa
#   bichos.log        eventos, pantallas, cada bicho, errores de Python y mensajes de Qt
#   bichos_fallo.log  volcado de pila si el proceso muere por un error nativo
#   bichos.estado     marca "estoy corriendo"; si al arrancar sigue ahí, el cierre anterior fue un crash
# ----------------------------------------------------------------------------
LOG = logging.getLogger("bichos")
LOG_PATH = os.path.join(DATA_DIR, "bichos.log")
STATE_PATH = os.path.join(DATA_DIR, "bichos.estado")
_keep = []


def _qt_msg(mode, ctx, msg):
    lvl = {QtMsgType.QtDebugMsg: logging.DEBUG, QtMsgType.QtInfoMsg: logging.INFO,
           QtMsgType.QtWarningMsg: logging.WARNING, QtMsgType.QtCriticalMsg: logging.ERROR,
           QtMsgType.QtFatalMsg: logging.CRITICAL}.get(mode, logging.INFO)
    LOG.log(lvl, "[Qt] %s", msg)
    if mode == QtMsgType.QtFatalMsg:  # Qt está por abortar: dejar la pila de Python antes de morir
        LOG.critical("[Qt] ERROR FATAL. Pila de Python en ese momento:\n%s", "".join(traceback.format_stack()))


class _ArchivoRotativo(logging.FileHandler):
    """Log con rotación por tamaño. Se hace a mano a propósito: logging.handlers arrastra al programa
    sockets, SMTP, HTTP y FTP que esta app no necesita (menos superficie de ataque)."""

    def __init__(self, path, max_bytes=500_000, copias=3):
        super().__init__(path, encoding="utf-8")
        self.max_bytes, self.copias = max_bytes, copias

    def emit(self, record):
        try:
            if self.stream is not None and self.stream.tell() >= self.max_bytes:
                self._rotar()
        except OSError:
            pass
        super().emit(record)

    def _rotar(self):
        self.stream.close()
        self.stream = None
        base = self.baseFilename
        for i in range(self.copias - 1, 0, -1):
            a = "%s.%d" % (base, i)
            if os.path.exists(a):
                os.replace(a, "%s.%d" % (base, i + 1))
        os.replace(base, base + ".1")
        self.stream = self._open()


_HOME = os.path.expanduser("~")


class _FormatoLimpio(logging.Formatter):
    """Como Formatter, pero tapa la ruta personal (C:\\Users\\nombre) que aparece en los errores."""

    def format(self, record):
        s = super().format(record)
        if len(_HOME) > 3:
            for h in (_HOME, _HOME.replace("\\", "/")):
                s = s.replace(h, "~").replace(h.lower(), "~").replace(h.upper(), "~")
        return s


def setup_logging():
    global LOG_PATH, STATE_PATH
    try:
        open(LOG_PATH, "a", encoding="utf-8").close()
    except OSError:  # carpeta de solo lectura: usar la temporal
        base = os.path.join(TEMP_DIR, "BichosPantalla")
        os.makedirs(base, exist_ok=True)
        LOG_PATH = os.path.join(base, "bichos.log")
        STATE_PATH = os.path.join(base, "bichos.estado")
    h = _ArchivoRotativo(LOG_PATH)
    h.setFormatter(_FormatoLimpio("%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S"))
    LOG.addHandler(h)
    LOG.setLevel(logging.DEBUG)
    try:
        ff = open(os.path.join(os.path.dirname(LOG_PATH), "bichos_fallo.log"), "a", encoding="utf-8")
        _keep.append(ff)
        faulthandler.enable(file=ff, all_threads=True)
    except Exception:
        LOG.exception("No pude activar faulthandler")
    sys.excepthook = lambda t, v, tb: LOG.critical("Excepción sin capturar:\n%s",
                                                    "".join(traceback.format_exception(t, v, tb)))
    sys.unraisablehook = lambda u: LOG.error("Excepción no elevable en %r:\n%s", u.object, "".join(
        traceback.format_exception(u.exc_type, u.exc_value, u.exc_traceback)))
    threading.excepthook = lambda a: LOG.critical("Excepción en hilo %s:\n%s", a.thread, "".join(
        traceback.format_exception(a.exc_type, a.exc_value, a.exc_traceback)))
    qInstallMessageHandler(_qt_msg)


def begin_session():
    """Detecta si la corrida anterior murió sin avisar y deja la marca de esta."""
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, encoding="utf-8") as f:
                LOG.warning("La corrida anterior NO terminó bien (no hubo 'Cierre normal'). Marca: %s",
                            f.read().strip())
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            f.write("pid=%d inicio=%s" % (os.getpid(), time.strftime("%Y-%m-%d %H:%M:%S")))
    except OSError:
        LOG.exception("No pude escribir la marca de estado")

    def bye():
        LOG.info("Cierre normal")
        try:
            os.remove(STATE_PATH)
        except OSError:
            pass
    atexit.register(bye)
    from PyQt6.QtCore import QT_VERSION_STR
    wv = sys.getwindowsversion()
    LOG.info("=== Inicio === pid=%d | Python %s | Qt %s | Windows %d.%d (build %d) | args=%s", os.getpid(),
             sys.version.split()[0], QT_VERSION_STR, wv.major, wv.minor, wv.build, " ".join(sys.argv[1:]))


def screen_id(s):
    """Identifica un monitor por su orden (P0, P1...) y no por su nombre de modelo (dato de hardware)."""
    try:
        return "P%d" % QGuiApplication.screens().index(s)
    except ValueError:
        return "P?"


def describe_screen(s):
    g = s.geometry()
    return "%s geom=(%d,%d %dx%d) dpr=%.2f dpi=%.0f" % (screen_id(s), g.x(), g.y(), g.width(), g.height(),
                                                       s.devicePixelRatio(), s.logicalDotsPerInch())


def log_screens(app):
    for s in app.screens():
        LOG.info("Pantalla %s%s", describe_screen(s), "  [principal]" if s is app.primaryScreen() else "")
    v = app.primaryScreen().virtualGeometry()
    LOG.info("Escritorio virtual: (%d,%d %dx%d)", v.x(), v.y(), v.width(), v.height())
    app.screenAdded.connect(lambda s: LOG.warning("Pantalla AGREGADA: %s", describe_screen(s)))
    app.screenRemoved.connect(lambda s: LOG.warning("Pantalla QUITADA"))
    for s in app.screens():
        s.geometryChanged.connect(lambda _g, s=s: LOG.warning("Pantalla cambió de geometría: %s", describe_screen(s)))


# ----------------------------------------------------------------------------
# utilidades
# ----------------------------------------------------------------------------
def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def wrap(a):
    return (a + math.pi) % TAU - math.pi


def smooth(t):
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def Q(r, g, b, a=255):
    return QColor(r, g, b, a)


_PEN = QPen()
_PEN.setCapStyle(Qt.PenCapStyle.RoundCap)
_PEN.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
BLACK = Q(0, 0, 0)


def line(p, a, b, w, color):
    _PEN.setColor(color)
    _PEN.setWidthF(w)
    p.setPen(_PEN)
    p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))


def tube(p, a, b, w, pal, lx, ly):
    """Segmento con aspecto de tubo brillante: borde oscuro, cuerpo, reflejo."""
    line(p, a, b, w, pal[0])
    line(p, a, b, w * 0.62, pal[1])
    o = w * 0.17
    line(p, (a[0] + lx * o, a[1] + ly * o), (b[0] + lx * o, b[1] + ly * o), w * 0.22, pal[2])


def polyline_path(pts):
    path = QPainterPath()
    path.moveTo(pts[0][0], pts[0][1])
    for x, y in pts[1:]:
        path.lineTo(x, y)
    return path


def ik(hx, hy, fx, fy, l1, l2, side, lift):
    """Cinemática inversa de 2 huesos. Devuelve (rodilla, pie) en coords locales."""
    dx, dy = fx - hx, fy - hy
    d = math.hypot(dx, dy)
    maxd = (l1 + l2) * 0.985
    if d > maxd:
        k = maxd / d
        dx *= k
        dy *= k
        fx, fy = hx + dx, hy + dy
        d = maxd
    d = max(d, 1e-3)
    ux, uy = dx / d, dy / d
    x = (d * d + l1 * l1 - l2 * l2) / (2.0 * d)
    h = math.sqrt(max(l1 * l1 - x * x, 0.0)) * (1.0 + 0.45 * lift)
    px, py = -uy, ux
    k1 = (hx + ux * x + px * h, hy + uy * x + py * h)
    k2 = (hx + ux * x - px * h, hy + uy * x - py * h)
    knee = k1 if side * k1[1] >= side * k2[1] else k2  # la rodilla siempre hacia afuera
    return knee, (fx, fy)


# ----------------------------------------------------------------------------
# paletas
# ----------------------------------------------------------------------------
ROACH_PALETTES = [
    dict(  # americana, marrón rojizo con banda clara en el pronoto
        wing=(Q(44, 18, 7), Q(110, 50, 18), Q(182, 108, 52)),
        ring=(Q(214, 178, 104), Q(160, 118, 58)), inner=(Q(104, 50, 20), Q(54, 24, 10)), stripes=False,
        leg=(Q(34, 14, 6), Q(96, 46, 18), Q(176, 112, 62)), edge=Q(26, 10, 4, 210),
        head=Q(48, 20, 8), abd=Q(40, 17, 8), spine=Q(30, 12, 5)),
    dict(  # oscura, caoba casi negra
        wing=(Q(18, 9, 6), Q(60, 28, 14), Q(128, 74, 42)),
        ring=(Q(132, 92, 52), Q(88, 56, 28)), inner=(Q(58, 28, 14), Q(30, 15, 8)), stripes=False,
        leg=(Q(20, 9, 5), Q(66, 31, 14), Q(130, 80, 46)), edge=Q(14, 6, 3, 220),
        head=Q(32, 14, 7), abd=Q(26, 11, 6), spine=Q(20, 8, 4)),
    dict(  # alemana, más clara y chica, con dos rayas en el pronoto
        wing=(Q(98, 62, 26), Q(168, 120, 60), Q(224, 184, 112)),
        ring=(Q(226, 196, 134), Q(190, 150, 88)), inner=(Q(70, 40, 16), Q(70, 40, 16)), stripes=True,
        leg=(Q(88, 56, 24), Q(160, 116, 60), Q(226, 190, 126)), edge=Q(70, 42, 16, 200),
        head=Q(96, 62, 28), abd=Q(100, 66, 30), spine=Q(78, 48, 20)),
]

SPIDER_PALETTES = [
    dict(  # doméstica parda
        abd=(Q(38, 26, 16), Q(96, 68, 42), Q(160, 124, 80)), ceph=(Q(52, 34, 20), Q(110, 78, 48), Q(172, 132, 86)),
        leg=(Q(36, 24, 14), Q(110, 80, 50), Q(190, 150, 100)), band=Q(40, 28, 16, 200), mark=Q(176, 140, 92, 120),
        hair=Q(190, 150, 100, 110), glossy=False),
    dict(  # lobo, gris pardusco con franja clara
        abd=(Q(40, 36, 32), Q(104, 94, 82), Q(168, 156, 138)), ceph=(Q(46, 40, 34), Q(112, 100, 86), Q(176, 164, 144)),
        leg=(Q(40, 36, 30), Q(112, 100, 86), Q(190, 178, 156)), band=Q(46, 40, 34, 190), mark=Q(210, 198, 170, 130),
        hair=Q(200, 190, 168, 120), glossy=False),
    dict(  # negra, lustrosa
        abd=(Q(6, 6, 8), Q(30, 28, 32), Q(96, 94, 104)), ceph=(Q(8, 8, 10), Q(36, 34, 38), Q(110, 108, 118)),
        leg=(Q(8, 8, 10), Q(40, 38, 42), Q(112, 110, 120)), band=Q(8, 8, 10, 160), mark=Q(120, 20, 18, 150),
        hair=Q(60, 58, 64, 90), glossy=True),
]


# ----------------------------------------------------------------------------
# geometría fija (en "unidades": el cuerpo de la cucaracha mide ~115)
# ----------------------------------------------------------------------------
def _wing(side):
    path = QPainterPath()
    path.moveTo(25, 0)
    path.cubicTo(27, side * 11, 12, side * 19, -10, side * 18.5)
    path.cubicTo(-32, side * 18, -52, side * 10, -58, side * 1.4)
    path.lineTo(-58, 0)
    path.closeSubpath()
    return path


WINGS = (_wing(-1), _wing(1))


def _veins():
    path = QPainterPath()
    for side in (-1, 1):
        for i in range(6):
            path.moveTo(21, side * (1.0 + i * 1.1))
            path.quadTo(-8, side * (5.0 + i * 3.0), -18 - i * 7.5, side * (16.8 - i * 2.2))
    return path


VEINS = _veins()


def _seam():
    path = QPainterPath()
    path.moveTo(23, 0)
    path.quadTo(-20, 1.0, -58, 0)
    return path


SEAM = _seam()


# ----------------------------------------------------------------------------
# especies
# ----------------------------------------------------------------------------
# ----------------------------------------------------------------------------
# cuerpos con fotos reales (sprites/*.png + *.json los genera herramientas/preparar_foto.py)
# Si no hay sprites para un bicho, se dibuja el cuerpo vectorial de siempre.
# ----------------------------------------------------------------------------
SPRITE_SPEC = {"cucaracha": (57.5, 115.5), "arana": (36.0, 98.0)}   # (x de la cabeza, largo del cuerpo) en unidades
SPRITES = {"cucaracha": [], "arana": []}
SPRITE_DIR = os.path.join(RES_DIR, "sprites")


class Sprite:
    def __init__(self, path, kind, meta):
        head_x, length = SPRITE_SPEC[kind]
        base = QImage(path)
        if base.isNull():
            raise ValueError("no pude leer " + path)
        base = base.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.w = length
        self.h = length * base.height() / base.width()
        self.x0 = head_x - length
        self.mips = []                       # (píxeles por unidad, imagen), de mayor a menor
        cur = base
        while True:
            self.mips.append((cur.width() / length, cur))
            if cur.width() < 90:
                break
            cur = cur.scaledToWidth(cur.width() // 2, Qt.TransformationMode.SmoothTransformation)
        small = self.mips[min(2, len(self.mips) - 1)][1]
        sil = QImage(small.size(), QImage.Format.Format_ARGB32_Premultiplied)
        sil.fill(0)
        sp = QPainter(sil)
        sp.drawImage(0, 0, small)
        sp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        sp.fillRect(sil.rect(), QColor(0, 0, 0))
        sp.end()
        self.sil = sil                       # silueta negra para la sombra
        self.leg = tuple(QColor(*c) for c in meta["leg"])
        self.spine = QColor(*meta.get("spine", meta["leg"][0]))
        self.edge = QColor(*meta.get("edge", meta["leg"][0]), 200)
        base_dir = os.path.dirname(path)
        self.femur = Strip(os.path.join(base_dir, meta["femur"]["png"]), meta["femur"]) if "femur" in meta else None
        self.pata = Strip(os.path.join(base_dir, meta["pata"]["png"]), meta["pata"]) if "pata" in meta else None

    def pick(self, ppu):
        """Imagen más chica que todavía tenga al menos ~1 píxel de foto por píxel de pantalla."""
        for p_, img in reversed(self.mips):
            if p_ >= ppu * 0.9:
                return img
        return self.mips[0][1]


class Strip:
    """Tramo de pata real (foto enderezada: base a la izquierda, punta a la derecha)."""

    def __init__(self, path, m):
        base = QImage(path)
        if base.isNull():
            raise ValueError("no pude leer " + path)
        base = base.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        self.w, self.h = base.width(), base.height()
        self.L, self.pad, self.t0 = m["largo"], m["pad"], m["grosor"]
        self.mips = [base]
        cur = base
        while cur.width() > 32 and cur.height() > 8:
            cur = cur.scaled(max(1, cur.width() // 2), max(1, cur.height() // 2), Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
            self.mips.append(cur)

    def pick(self, scr):
        """scr = píxeles de pantalla por píxel de imagen; se usa la mitad (1/2, 1/4...) que no pierda detalle."""
        k = 0 if scr >= 1.0 else min(len(self.mips) - 1, int(math.floor(math.log2(1.0 / scr))))
        return self.mips[k]


def draw_strip(p, st, a, b, wu, s):
    """Dibuja el tramo de pata `st` desde a (base) hasta b (punta); wu = grosor deseado en la base (unidades)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1e-3
    su = ln / st.L                                   # unidades por píxel a lo largo
    sv = clamp(su, 0.6 * wu / st.t0, 1.8 * wu / st.t0)   # y a lo ancho: proporción natural, acotada
    img = st.pick(max(su, sv) * s)
    p.save()
    p.translate(a[0], a[1])
    p.rotate(math.degrees(math.atan2(dy, dx)))
    p.drawImage(QRectF(-st.pad * su, -st.h * sv / 2, st.w * su, st.h * sv), img)
    p.restore()


def strip_leg(p, lg, c, pal, lx, ly):
    """Pata con texturas reales: resto de la pata (rodilla->pie) y, si hay foto, fémur (cadera->rodilla);
    si no hay foto de fémur se dibuja un tubo con los colores de la foto."""
    spr = c.sprite
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    draw_strip(p, spr.pata, lg.knee, lg.footl, lg.wt, c.s)
    if spr.femur is not None:
        draw_strip(p, spr.femur, lg.hip, lg.knee, lg.wf, c.s)
    else:  # un solo tubo (sin cortes), más claro como el fémur real, que es ancho y anaranjado
        tube(p, lg.hip, lg.knee, lg.wf * 1.0, (spr.leg[0], spr.leg[1], spr.leg[2]), lx, ly)
    p.setPen(Qt.PenStyle.NoPen)                      # tapa la articulación
    p.setBrush(spr.leg[0])
    p.drawEllipse(QPointF(lg.knee[0], lg.knee[1]), lg.wt * 0.42, lg.wt * 0.42)


def load_sprites():
    import json
    SPRITES["cucaracha"].clear()
    SPRITES["arana"].clear()
    if not os.path.isdir(SPRITE_DIR):
        return
    for fn in sorted(os.listdir(SPRITE_DIR)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(SPRITE_DIR, fn), encoding="utf-8") as f:
                meta = json.load(f)
            kind = meta["tipo"]
            for v in meta["variantes"]:
                SPRITES[kind].append(Sprite(os.path.join(SPRITE_DIR, v["png"]), kind, v))
        except Exception:
            LOG.exception("No pude cargar el sprite %s; se usará el dibujo vectorial", fn)
    LOG.info("Sprites con fotos reales: %d de cucaracha, %d de araña", len(SPRITES["cucaracha"]),
             len(SPRITES["arana"]))


def draw_sprite(p, spr, c):
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.drawImage(QRectF(spr.x0, -spr.h / 2, spr.w, spr.h), spr.pick(c.s))


class Spec:
    pass


def _mirror_legs(defs, wf, wt, ft):
    out = []
    for i, (hip, home, l1, l2) in enumerate(defs):
        for side in (-1, 1):
            out.append(dict(hip=(hip[0], hip[1] * side), home=(home[0], home[1] * side), l1=l1, l2=l2,
                            side=side, off=0.0 if (i + (0 if side > 0 else 1)) % 2 == 0 else 0.5,
                            wf=wf, wt=wt, ft=ft, seed=i * 2 + (side > 0)))
    return out


ROACH = Spec()
ROACH.name = "cucaracha"
ROACH.R = 185
ROACH.cycle = 62
ROACH.vmin, ROACH.vmax, ROACH.vdash = 220, 580, 780
ROACH.accel, ROACH.decel, ROACH.turn = 2600, 4200, 8.0
ROACH.run_t, ROACH.pause_t, ROACH.pause_p, ROACH.dash_p = (0.4, 1.7), (0.2, 1.3), 0.5, 0.18
ROACH.wander, ROACH.flee_r = 0.9, 190
ROACH.sway = 0.05
ROACH.legdefs = _mirror_legs([((34, 12), (64, 46), 30, 38),
                              ((14, 16), (14, 68), 36, 44),
                              ((-6, 18), (-52, 62), 42, 52)], 7.4, 4.5, 2.1)

SPIDER = Spec()
SPIDER.name = "araña"
SPIDER.R = 160
SPIDER.cycle = 64
SPIDER.vmin, SPIDER.vmax, SPIDER.vdash = 120, 340, 540
SPIDER.accel, SPIDER.decel, SPIDER.turn = 900, 1800, 3.6
SPIDER.run_t, SPIDER.pause_t, SPIDER.pause_p, SPIDER.dash_p = (0.8, 2.4), (0.4, 1.8), 0.45, 0.15
SPIDER.wander, SPIDER.flee_r = 0.6, 170
SPIDER.sway = 0.03
SPIDER.legdefs = _mirror_legs([((24, 8), (76, 46), 38, 50),
                               ((16, 10), (54, 72), 38, 50),
                               ((8, 10), (-8, 72), 38, 50),
                               ((0, 8), (-58, 54), 42, 54)], 5.0, 3.6, 1.9)


class Leg:
    __slots__ = ("hip", "home", "l1", "l2", "side", "off", "wf", "wt", "ft", "seed",
                 "foot", "start", "swing", "lift", "knee", "footl")

    def __init__(self, d):
        for k, v in d.items():
            setattr(self, k, v)
        self.foot = (0.0, 0.0)
        self.start = (0.0, 0.0)
        self.swing = False
        self.lift = 0.0
        self.knee = d["hip"]
        self.footl = d["home"]


# ----------------------------------------------------------------------------
# criatura: comportamiento + marcha (sin nada de ventanas)
# ----------------------------------------------------------------------------
class Creature:
    SW = 0.4  # fracción del ciclo en que una pata está en el aire

    def __init__(self, spec, scale, start, target, variant=0, debug_speed=None):
        self.spec = spec
        self.s = scale
        self.s_base = scale   # tamaño elegido por el usuario (sin ajuste por densidad del monitor)
        self.s_goal = scale   # tamaño al que tiende según el monitor en que esté
        self.variant = variant
        lst = SPRITES["cucaracha" if spec is ROACH else "arana"]
        self.sprite = lst[variant] if variant < len(lst) else None   # cuerpo con foto real (o None = vectorial)
        self.x, self.y = start
        self.target = target
        self.a = math.atan2(target[1] - start[1], target[0] - start[0])
        self.ad = self.a
        self.ca, self.sa = math.cos(self.a), math.sin(self.a)
        self.v = 0.0
        self.vt = random.uniform(spec.vmin, spec.vmax) * scale
        self.state = "run"
        self.timer = random.uniform(1.0, 1.8)
        self.wander = 0.0
        self.u = random.random()
        self.t = random.random() * 10
        self.act = 0.5
        self.light = (-0.5, -0.8)
        self.debug = debug_speed
        self.dead = False
        self.age = 0.0
        self.legs = [Leg(d) for d in spec.legdefs]
        self.limbs = []  # antenas / palpos: lista de polilíneas en coords locales
        self.ph = [random.random() * TAU for _ in range(4)]
        # cerdas del abdomen de la araña (fijas)
        self.fuzz = [(random.random() * TAU, random.uniform(2.5, 5.5)) for _ in range(46)]
        self.hairs = [[(random.uniform(0.15, 0.95), random.choice((-1, 1)), random.uniform(2.0, 4.2))
                       for _ in range(7)] for _ in range(16)]
        for lg in self.legs:
            lg.foot = self.l2w(*lg.home)
        self._legs_pose()
        self._limbs()

    # --- transformaciones local <-> mundo
    def l2w(self, lx, ly):
        return (self.x + (lx * self.ca - ly * self.sa) * self.s,
                self.y + (lx * self.sa + ly * self.ca) * self.s)

    def w2l(self, wx, wy):
        dx, dy = wx - self.x, wy - self.y
        return ((dx * self.ca + dy * self.sa) / self.s, (-dx * self.sa + dy * self.ca) / self.s)

    # --- paso de simulación
    def update(self, dt, cursor=None, flee=True):
        if self.s_goal != self.s:  # cambio de monitor: crecer/achicarse con suavidad, sin saltos
            self.s += (self.s_goal - self.s) * min(1.0, 6.0 * dt)
            if abs(self.s_goal - self.s) < 1e-3:
                self.s = self.s_goal
        sp, s = self.spec, self.s
        self.t += dt
        self.age += dt
        tx, ty = self.target
        to_t = math.atan2(ty - self.y, tx - self.x)
        dist_t = math.hypot(tx - self.x, ty - self.y)

        if self.debug is not None:
            self.v = self.vt = self.debug
            desired = self.a
        else:
            self.timer -= dt
            if self.timer <= 0:
                if self.state == "run" and random.random() < sp.pause_p:
                    self.state = "pause"
                    self.timer = random.uniform(*sp.pause_t)
                    self.vt = 0.0
                else:
                    self.state = "run"
                    self.timer = random.uniform(*sp.run_t)
                    self.vt = (sp.vdash if random.random() < sp.dash_p else random.uniform(sp.vmin, sp.vmax)) * s

            flee_dir = None
            if flee and cursor is not None:
                dx, dy = self.x - cursor[0], self.y - cursor[1]
                if math.hypot(dx, dy) < sp.flee_r * s:
                    flee_dir = math.atan2(dy, dx)
                    if self.state == "pause" or self.vt < sp.vmax * s * 0.8:
                        self.state = "run"
                        self.timer = random.uniform(0.6, 1.2)
                        self.vt = sp.vdash * s

            k = min(1.0, dist_t / (300.0 * s))
            self.wander += -self.wander * 1.8 * dt + random.gauss(0, 1) * sp.wander * math.sqrt(dt) * k
            self.wander = clamp(self.wander, -0.9, 0.9)
            desired = to_t + self.wander
            if flee_dir is not None:
                desired = flee_dir + 0.5 * wrap(to_t - flee_dir)

            acc = sp.accel * s if self.vt > self.v else sp.decel * s
            self.v += clamp(self.vt - self.v, -acc * dt, acc * dt)

        turn = sp.turn * (0.25 + 0.75 * clamp(self.v / (sp.vmax * s * 0.5), 0.0, 1.0))
        self.a += clamp(wrap(desired - self.a), -turn * dt, turn * dt)
        self.x += math.cos(self.a) * self.v * dt
        self.y += math.sin(self.a) * self.v * dt

        # --- marcha: la fase avanza con la distancia recorrida
        spd = clamp(self.v / (sp.vmax * s), 0.0, 1.3)
        cyc = sp.cycle * s * (0.8 + 0.4 * min(spd, 1.0))
        self.lead = cyc * (1.0 - self.SW) * 0.5
        sw = self.SW
        if self.v > 6 * s:
            self.u = (self.u + self.v * dt / cyc) % 1.0
        else:  # parado: terminar el paso en curso y dejar las patas apoyadas
            uu = self.u
            if not ((sw <= uu < 0.5) or (0.5 + sw <= uu < 1.0)):
                self.u = (self.u + 2.6 * dt) % 1.0

        self.ad = self.a + sp.sway * spd * math.sin(TAU * self.u)
        self.ca, self.sa = math.cos(self.ad), math.sin(self.ad)
        L = (-0.45, -0.75)
        self.light = (L[0] * self.ca + L[1] * self.sa, -L[0] * self.sa + L[1] * self.ca)

        # --- patas
        for lg in self.legs:
            v = (self.u - lg.off) % 1.0
            tgt = self.l2w(lg.home[0] + self.lead / s, lg.home[1])
            if v < sw:
                if not lg.swing:
                    lg.swing = True
                    lg.start = lg.foot
                t = v / sw
                e = smooth(t)
                lg.foot = (lerp(lg.start[0], tgt[0], e), lerp(lg.start[1], tgt[1], e))
                lg.lift = math.sin(math.pi * t)
            else:
                if lg.swing:
                    lg.swing = False
                    lg.foot = tgt
                lg.lift = 0.0
        self._legs_pose()

        self.act += ((1.0 if self.state == "pause" else 0.45) - self.act) * min(1.0, 4.0 * dt)
        self._limbs()

        # --- fin del recorrido
        if self.debug is None:
            if dist_t < 50 * s or self.age > 70:
                self.dead = True

    def _legs_pose(self):
        for lg in self.legs:
            fx, fy = self.w2l(*lg.foot)
            lg.knee, lg.footl = ik(lg.hip[0], lg.hip[1], fx, fy, lg.l1, lg.l2, lg.side, lg.lift)

    def _limbs(self):
        t, act = self.t, self.act
        self.limbs = []
        if self.spec is ROACH:
            for i, side in enumerate((-1, 1)):
                ph = self.ph[i]
                ang = side * (0.62 + 0.30 * math.sin(1.4 * t + ph) * (0.35 + act))
                x, y = 54.0, side * 3.0
                pts = [(x, y)]
                for k in range(14):
                    ang += side * 0.036 + 0.075 * math.sin(t * (2.6 + 4.5 * act) + ph + k * 0.5) * act * (1 + k * 0.07)
                    x += 7.6 * math.cos(ang)
                    y += 7.6 * math.sin(ang)
                    pts.append((x, y))
                self.limbs.append(pts)
        else:
            for i, side in enumerate((-1, 1)):
                ph = self.ph[i]
                a1 = side * (0.50 + 0.22 * math.sin(t * 6.0 + ph) * (0.35 + act))
                p0 = (31.0, side * 4.5)
                p1 = (p0[0] + 10.5 * math.cos(a1), p0[1] + 10.5 * math.sin(a1))
                a2 = side * (-0.35 + 0.35 * math.sin(t * 6.0 + ph + 1.1) * (0.35 + act))
                p2 = (p1[0] + 9.0 * math.cos(a2), p1[1] + 9.0 * math.sin(a2))
                self.limbs.append([p0, p1, p2])

    # --- dibujo
    def paint(self, p, ox, oy, side, shadow):
        s = self.s
        k = shadow.width() / float(side)
        shadow.fill(0)
        sp = QPainter(shadow)
        sp.setRenderHint(QPainter.RenderHint.Antialiasing)
        sp.scale(k, k)
        sp.translate(self.x - ox + 3.5 * s, self.y - oy + 6.0 * s)
        sp.rotate(math.degrees(self.ad))
        sp.scale(s, s)
        (shadow_roach if self.spec is ROACH else shadow_spider)(sp, self)
        sp.end()
        p.save()
        p.setOpacity(0.36)
        p.drawImage(QRectF(0, 0, side, side), shadow)
        p.restore()
        p.save()
        p.translate(self.x - ox, self.y - oy)
        p.rotate(math.degrees(self.ad))
        p.scale(s, s)
        (draw_roach if self.spec is ROACH else draw_spider)(p, self)
        p.restore()


# ----------------------------------------------------------------------------
# dibujo: cucaracha
# ----------------------------------------------------------------------------
def _lower(lg, kn, ft, bow):
    """Devuelve at(t): punto del tramo rodilla->pie con un arco suave hacia afuera."""
    vx, vy = ft[0] - kn[0], ft[1] - kn[1]
    ln = math.hypot(vx, vy) or 1.0
    nx, ny = -vy / ln, vx / ln
    if lg.side * ny < 0:
        nx, ny = -nx, -ny
    bx, by = nx * bow, ny * bow

    def at(t):
        w = math.sin(math.pi * t)
        return (kn[0] + vx * t + bx * w, kn[1] + vy * t + by * w)
    return at, (vx / ln, vy / ln), (nx, ny)


def _mid(a, b):
    return ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)


def _roach_leg(p, lg, pal, lx, ly):
    hip, kn, ft = lg.hip, lg.knee, lg.footl
    m = _mid(hip, kn)
    tube(p, hip, m, lg.wf, pal["leg"], lx, ly)                        # fémur (grueso)
    tube(p, m, kn, lg.wf * 0.86, pal["leg"], lx, ly)
    at, (ux, uy), _ = _lower(lg, kn, ft, 1.8)
    a, b, c = at(0.36), at(0.70), at(0.90)
    tube(p, kn, a, lg.wt, pal["leg"], lx, ly)                         # tibia en tramos que se afinan
    tube(p, a, b, lg.wt * 0.82, pal["leg"], lx, ly)
    tube(p, b, c, lg.wt * 0.62, pal["leg"], lx, ly)
    tube(p, c, ft, lg.ft, pal["leg"], lx, ly)                         # tarso
    for i, tt in enumerate((0.16, 0.30, 0.44, 0.58, 0.72, 0.84)):     # espinas de la tibia
        sx, sy = at(tt)
        sd = 1 if i % 2 == 0 else -1
        dx = -uy * sd * 0.8 + ux * 0.6
        dy = ux * sd * 0.8 + uy * 0.6
        line(p, (sx, sy), (sx + dx * 2.6, sy + dy * 2.6), 0.75, pal["spine"])
    line(p, ft, (ft[0] + ux * 2.4, ft[1] + uy * 2.4), 1.0, pal["spine"])  # uña


def draw_roach(p, c):
    pal = ROACH_PALETTES[c.variant % len(ROACH_PALETTES)]
    spr = c.sprite
    if spr is not None:  # los colores de las patas salen de la propia foto
        pal = dict(pal, leg=spr.leg, spine=spr.spine, edge=spr.edge)
    lx, ly = c.light
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for lg in c.legs:
        if spr is not None and spr.pata is not None:
            strip_leg(p, lg, c, pal, lx, ly)
        else:
            _roach_leg(p, lg, pal, lx, ly)
    # cercos
    for sd in (-1, 1):
        if spr is not None:
            line(p, (-54, sd * 2.2), (-63, sd * 4.4), 1.7, pal["leg"][0])
        else:
            line(p, (-56, sd * 2.4), (-67, sd * 5.2), 2.4, pal["spine"])
    p.setPen(Qt.PenStyle.NoPen)
    if spr is not None:
        draw_sprite(p, spr, c)
    else:
        _roach_vector_body(p, c, pal, lx, ly)
    _roach_antennae(p, c, pal)


def _roach_vector_body(p, c, pal, lx, ly):
    # abdomen (asoma bajo las alas)
    p.setBrush(pal["abd"])
    p.drawEllipse(QPointF(-31, 0), 31.5, 18)
    # cabeza
    p.setBrush(pal["head"])
    p.drawEllipse(QPointF(51, 0), 7.5, 7.2)
    # alas con degradé y reborde
    g = QRadialGradient(-8, 0, 50, -8 + lx * 17, ly * 10)
    g.setColorAt(0.0, pal["wing"][2])
    g.setColorAt(0.42, pal["wing"][1])
    g.setColorAt(1.0, pal["wing"][0])
    _PEN.setColor(pal["edge"])
    _PEN.setWidthF(1.0)
    p.setPen(_PEN)
    p.setBrush(g)
    p.drawPath(WINGS[0])
    p.drawPath(WINGS[1])
    # nervaduras
    vc = QColor(pal["edge"])
    vc.setAlpha(80)
    _PEN.setColor(vc)
    _PEN.setWidthF(0.6)
    p.setPen(_PEN)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(VEINS)
    sc = QColor(pal["edge"])
    sc.setAlpha(230)
    _PEN.setColor(sc)
    _PEN.setWidthF(1.1)
    p.setPen(_PEN)
    p.drawPath(SEAM)
    # brillo alargado sobre las alas
    p.setPen(Qt.PenStyle.NoPen)
    p.save()
    p.translate(-8 + lx * 11, ly * 9)
    p.scale(1.0, 0.24)
    hg = QRadialGradient(0, 0, 26)
    hg.setColorAt(0.0, Q(255, 244, 220, 120))
    hg.setColorAt(1.0, Q(255, 244, 220, 0))
    p.setBrush(hg)
    p.drawEllipse(QPointF(0, 0), 26, 26)
    p.restore()
    # pronoto (escudo)
    pg = QRadialGradient(31, 0, 21, 31 + lx * 7, ly * 6)
    pg.setColorAt(0.0, pal["ring"][0])
    pg.setColorAt(1.0, pal["ring"][1])
    _PEN.setColor(pal["edge"])
    _PEN.setWidthF(0.9)
    p.setPen(_PEN)
    p.setBrush(pg)
    p.drawEllipse(QPointF(31, 0), 18.5, 15.6)
    p.setPen(Qt.PenStyle.NoPen)
    if pal["stripes"]:
        p.setBrush(pal["inner"][0])
        for sd in (-1, 1):
            p.drawRoundedRect(QRectF(21, sd * 5.2 - 2.3, 19, 4.6), 2.3, 2.3)
    else:
        ig = QRadialGradient(31, 0, 13, 31 + lx * 4, ly * 3)
        ig.setColorAt(0.0, pal["inner"][0])
        ig.setColorAt(1.0, pal["inner"][1])
        p.setBrush(ig)
        p.drawEllipse(QPointF(31.5, 0), 12.8, 10.6)
    p.save()
    p.translate(31 + lx * 6, ly * 5)
    p.scale(1.0, 0.7)
    bg = QRadialGradient(0, 0, 9)
    bg.setColorAt(0.0, Q(255, 250, 235, 105))
    bg.setColorAt(1.0, Q(255, 250, 235, 0))
    p.setBrush(bg)
    p.drawEllipse(QPointF(0, 0), 9, 9)
    p.restore()
    # ojos
    for sd in (-1, 1):
        p.setBrush(Q(8, 4, 3))
        p.drawEllipse(QPointF(54.2, sd * 4.4), 2.2, 2.0)
        p.setBrush(Q(255, 255, 255, 200))
        p.drawEllipse(QPointF(54.2 + lx * 0.8, sd * 4.4 + ly * 0.8), 0.6, 0.6)
def _roach_antennae(p, c, pal):
    for pts in c.limbs:
        _PEN.setColor(pal["leg"][0])
        p.setBrush(Qt.BrushStyle.NoBrush)
        for a, b, w in ((0, 5, 2.0), (4, 9, 1.55), (8, 12, 1.15), (11, 15, 0.8)):  # se afina hacia la punta
            _PEN.setWidthF(w)
            p.setPen(_PEN)
            p.drawPath(polyline_path(pts[a:b]))


def shadow_roach(p, c):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(BLACK)
    if c.sprite is not None:
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(QRectF(c.sprite.x0, -c.sprite.h / 2, c.sprite.w, c.sprite.h), c.sprite.sil)
    else:
        p.drawEllipse(QPointF(-31, 0), 32, 18.5)
        p.drawEllipse(QPointF(31, 0), 18.5, 15.6)
        p.drawEllipse(QPointF(51, 0), 7.5, 7.2)
    for lg in c.legs:
        line(p, lg.hip, lg.knee, lg.wf * 0.8, BLACK)
        line(p, lg.knee, lg.footl, lg.wt * 0.8, BLACK)
    for pts in c.limbs:
        _PEN.setColor(BLACK)
        _PEN.setWidthF(1.6)
        p.setPen(_PEN)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(polyline_path(pts))


# ----------------------------------------------------------------------------
# dibujo: araña
# ----------------------------------------------------------------------------
def _spider_leg(p, lg, c, pal, lx, ly, idx):
    hip, kn, ft = lg.hip, lg.knee, lg.footl
    lpal = pal["leg"]
    m = _mid(hip, kn)
    tube(p, hip, m, lg.wf, lpal, lx, ly)                               # fémur
    tube(p, m, kn, lg.wf * 0.9, lpal, lx, ly)
    at, (ux, uy), (nx, ny) = _lower(lg, kn, ft, 3.4)
    a, b, e = at(0.34), at(0.68), at(0.88)
    tube(p, kn, a, lg.wt, lpal, lx, ly)                                # patela-tibia
    tube(p, a, b, lg.wt * 0.82, lpal, lx, ly)                          # metatarso
    tube(p, b, e, lg.wt * 0.62, lpal, lx, ly)
    tube(p, e, ft, lg.ft, lpal, lx, ly)                                # tarso
    # anillos oscuros en las articulaciones
    for q, w in ((kn, lg.wt), (a, lg.wt * 0.82)):
        r = w * 0.52
        line(p, (q[0] - nx * r, q[1] - ny * r), (q[0] + nx * r, q[1] + ny * r), 1.5, pal["band"])
    # pelitos
    hc = pal["hair"]
    for tt, sd, hl in c.hairs[idx % len(c.hairs)]:
        bx, by = at(tt)
        line(p, (bx, by), (bx + (nx * sd * 0.9 + ux * 0.4) * hl, by + (ny * sd * 0.9 + uy * 0.4) * hl), 0.5, hc)
    fx_, fy_ = (kn[0] - hip[0]), (kn[1] - hip[1])
    fl = math.hypot(fx_, fy_) or 1.0
    for tt, sd, hl in c.hairs[(idx + 5) % len(c.hairs)][:5]:
        bx, by = hip[0] + fx_ * tt, hip[1] + fy_ * tt
        line(p, (bx, by), (bx + (-fy_ / fl * sd * 0.9 + fx_ / fl * 0.4) * hl, by + (fx_ / fl * sd * 0.9 + fy_ / fl * 0.4) * hl), 0.5, hc)


def draw_spider(p, c):
    pal = SPIDER_PALETTES[c.variant % len(SPIDER_PALETTES)]
    spr = c.sprite
    if spr is not None:  # colores de patas, anillos y pelitos tomados de la foto
        d, lt = spr.leg[0], spr.leg[2]
        pal = dict(pal, leg=spr.leg, band=QColor(d.red(), d.green(), d.blue(), 190),
                   hair=QColor(lt.red(), lt.green(), lt.blue(), 120), abd=(d, d, d))
    lx, ly = c.light
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, lg in enumerate(c.legs):
        if spr is not None and spr.pata is not None:
            strip_leg(p, lg, c, pal, lx, ly)
        else:
            _spider_leg(p, lg, c, pal, lx, ly, i)
    p.setPen(Qt.PenStyle.NoPen)
    if spr is not None:
        draw_sprite(p, spr, c)
    else:
        _spider_vector_body(p, c, pal, lx, ly)
    _spider_front(p, c, pal, lx, ly, 3.5 if spr is not None else 0.0)


def _spider_vector_body(p, c, pal, lx, ly):
    # hileras (rabito)
    p.setBrush(pal["abd"][0])
    p.drawEllipse(QPointF(-60, 0), 4.5, 5.0)
    # abdomen
    ag = QRadialGradient(-30, 0, 34, -30 + lx * 15, ly * 11)
    ag.setColorAt(0.0, pal["abd"][2])
    ag.setColorAt(0.45, pal["abd"][1])
    ag.setColorAt(1.0, pal["abd"][0])
    # pelusa del borde
    fc = pal["hair"]
    for ang, ln in c.fuzz:
        ex, ey = -30 + 30.5 * math.cos(ang), 22.5 * math.sin(ang)
        line(p, (ex, ey), (ex + math.cos(ang) * ln, ey + math.sin(ang) * ln * 0.8), 0.55, fc)
    _PEN.setColor(pal["abd"][0])
    _PEN.setWidthF(1.0)
    p.setPen(_PEN)
    p.setBrush(ag)
    p.drawEllipse(QPointF(-30, 0), 30, 22)
    # dibujo dorsal: franja y chevrones
    mk = pal["mark"]
    for i in range(5):
        x0 = -14 - i * 8.2
        wdt = 9.0 - i * 1.0
        line(p, (x0, 0), (x0 - 6.5, -wdt), 2.0, mk)
        line(p, (x0, 0), (x0 - 6.5, wdt), 2.0, mk)
    line(p, (-8, 0), (-54, 0), 2.2, mk)
    p.setPen(Qt.PenStyle.NoPen)
    # brillo del abdomen
    p.save()
    p.translate(-30 + lx * 12, ly * 9)
    p.scale(1.0, 0.62)
    hg = QRadialGradient(0, 0, 15)
    hg.setColorAt(0.0, Q(255, 250, 240, 150 if pal["glossy"] else 80))
    hg.setColorAt(1.0, Q(255, 250, 240, 0))
    p.setBrush(hg)
    p.drawEllipse(QPointF(0, 0), 15, 15)
    p.restore()
    # marca roja de la negra
    if pal["glossy"]:
        p.setBrush(mk)
        p.drawEllipse(QPointF(-28, 0), 4.2, 6.0)
    # cefalotórax
    cg = QRadialGradient(12, 0, 22, 12 + lx * 9, ly * 7)
    cg.setColorAt(0.0, pal["ceph"][2])
    cg.setColorAt(0.5, pal["ceph"][1])
    cg.setColorAt(1.0, pal["ceph"][0])
    path = QPainterPath()
    path.moveTo(32, 0)
    path.cubicTo(32, -8, 26, -15.5, 11, -15.5)
    path.cubicTo(-3, -15.5, -9, -8, -9, 0)
    path.cubicTo(-9, 8, -3, 15.5, 11, 15.5)
    path.cubicTo(26, 15.5, 32, 8, 32, 0)
    _PEN.setColor(pal["ceph"][0])
    _PEN.setWidthF(1.0)
    p.setPen(_PEN)
    p.setBrush(cg)
    p.drawPath(path)
    # fóvea y surcos
    gc = QColor(pal["ceph"][0])
    gc.setAlpha(200)
    line(p, (7, 0), (-3, 0), 1.6, gc)
    for sd in (-1, 1):
        line(p, (6, sd * 1.5), (1, sd * 8.5), 0.8, gc)
        line(p, (6, sd * 1.5), (11, sd * 8.0), 0.8, gc)
    p.setPen(Qt.PenStyle.NoPen)
    p.save()
    p.translate(14 + lx * 7, ly * 6)
    p.scale(1.0, 0.7)
    bg = QRadialGradient(0, 0, 10)
    bg.setColorAt(0.0, Q(255, 250, 240, 140 if pal["glossy"] else 80))
    bg.setColorAt(1.0, Q(255, 250, 240, 0))
    p.setBrush(bg)
    p.drawEllipse(QPointF(0, 0), 10, 10)
    p.restore()
def _spider_front(p, c, pal, lx, ly, dx):
    """Quelíceros, palpos y ojos (animados/vectoriales, van sobre cualquier cuerpo). dx adelanta la cara."""
    p.setPen(Qt.PenStyle.NoPen)
    for sd in (-1, 1):
        p.setBrush(pal["abd"][0])
        p.drawEllipse(QPointF(32.5 + dx, sd * 3.0), 3.2, 2.4)
        line(p, (34.5 + dx, sd * 2.6), (38.0 + dx, sd * 1.8), 0.9, pal["band"])
    # palpos
    fine = dx > 0  # con cuerpo de foto: palpos y ojos más discretos
    for pts in c.limbs:
        line(p, pts[0], pts[1], 2.7 * (0.8 if fine else 1.0), pal["leg"][0])
        line(p, pts[0], pts[1], 1.7 * (0.8 if fine else 1.0), pal["leg"][1])
        line(p, pts[1], pts[2], 2.3 * (0.8 if fine else 1.0), pal["leg"][0])
        line(p, pts[1], pts[2], 1.3 * (0.8 if fine else 1.0), pal["leg"][1])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(pal["leg"][0])
        p.drawEllipse(QPointF(pts[2][0], pts[2][1]), 1.6 if fine else 2.0, 1.6 if fine else 2.0)
    # ojos (8)
    p.setPen(Qt.PenStyle.NoPen)
    eyes = [(28.0 + dx, 2.3, 1.7), (28.4 + dx, 5.6, 1.5), (24.5 + dx, 4.0, 2.3), (21.5 + dx, 8.2, 1.4)]
    if fine:   # con foto: dos ojos grandes al frente (los demás ya están en la foto)
        eyes = [(30.0 + dx, 2.6, 1.5), (27.0 + dx, 5.2, 1.0)]
    for ex, ey, er in eyes:
        for sd in (-1, 1):
            p.setBrush(Q(6, 6, 8))
            p.drawEllipse(QPointF(ex, ey * sd), er, er)
            p.setBrush(Q(255, 255, 255, 190))
            p.drawEllipse(QPointF(ex + lx * er * 0.45, ey * sd + ly * er * 0.45), er * 0.32, er * 0.32)


def shadow_spider(p, c):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(BLACK)
    if c.sprite is not None:
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(QRectF(c.sprite.x0, -c.sprite.h / 2, c.sprite.w, c.sprite.h), c.sprite.sil)
    else:
        p.drawEllipse(QPointF(-30, 0), 31, 23)
        p.drawEllipse(QPointF(11, 0), 20, 16)
    for lg in c.legs:
        line(p, lg.hip, lg.knee, lg.wf * 0.9, BLACK)
        line(p, lg.knee, lg.footl, lg.wt * 0.9, BLACK)


# ----------------------------------------------------------------------------
# ventana transparente que sigue a la criatura
# ----------------------------------------------------------------------------
SHADOW_K = 0.36


class BugWindow(QWidget):
    def __init__(self, creature, s_max=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.c = creature
        # tamaño fijo para el mayor escalado posible (según monitor) y bloqueado: si Qt/Windows
        # intentan reescalarla al cambiar de monitor, no pueden
        self.side = int(math.ceil(2 * creature.spec.R * (s_max or creature.s)))
        self.setFixedSize(self.side, self.side)
        n = int(self.side * SHADOW_K) + 1
        self.shadow = QImage(n, n, QImage.Format.Format_ARGB32_Premultiplied)
        self.ox = self.oy = 0
        self._place()

    def _place(self):
        self.ox = int(round(self.c.x - self.side / 2))
        self.oy = int(round(self.c.y - self.side / 2))
        self.move(self.ox, self.oy)
        if self.width() != self.side or self.height() != self.side:  # no debería pasar; si pasa, queda en el log
            LOG.warning("bicho#%s: la ventana cambió de tamaño a %dx%d (debía ser %d); la restauro",
                        getattr(self, "bid", "?"), self.width(), self.height(), self.side)
            self.setGeometry(self.ox, self.oy, self.side, self.side)
            self.bad_resizes = getattr(self, "bad_resizes", 0) + 1
            if self.bad_resizes > 20:
                LOG.error("bicho#%s: demasiados cambios de tamaño; lo saco de pantalla", getattr(self, "bid", "?"))
                self.c.dead = True

    def step(self, dt, cursor, flee):
        self.c.update(dt, cursor, flee)
        self._place()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            self.c.paint(p, self.ox, self.oy, self.side, self.shadow)
        except Exception:
            LOG.exception("Error al dibujar bicho#%s", getattr(self, "bid", "?"))
            self.c.dead = True
        finally:
            p.end()


# ----------------------------------------------------------------------------
# configuración
# ----------------------------------------------------------------------------
FREQS = {  # clave: (texto, mínimo s, máximo s)
    "prueba": ("Muy seguido (cada 5–15 s, para probar)", 5, 15),
    "alta": ("Seguido (cada 20–60 s)", 20, 60),
    "media": ("A veces (cada 1–4 min)", 60, 240),
    "baja": ("Raro (cada 5–15 min)", 300, 900),
}
KINDS = {"azar": "Cualquiera (al azar)", "cucaracha": "Solo cucarachas", "arana": "Solo arañas"}
SIZES = {"chico": ("Chico", 0.7), "medio": ("Mediano", 1.0), "grande": ("Grande", 1.5), "enorme": ("Enorme", 2.1)}
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "BichosPantalla"


def startup_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_NAME)
            return True
    except Exception:
        return False


def set_startup(on):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                if getattr(sys, "frozen", False):
                    cmd = '"%s"' % sys.executable
                else:
                    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                    cmd = '"%s" "%s"' % (pyw if os.path.exists(pyw) else sys.executable, os.path.abspath(__file__))
                winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(k, RUN_NAME)
                except FileNotFoundError:
                    pass
    except Exception:
        traceback.print_exc()


def tray_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.translate(32, 33)
    p.rotate(-90)
    p.scale(0.42, 0.42)
    pal = ROACH_PALETTES[0]
    for sd in (-1, 1):
        for hx, fx, fy in ((34, 62, 40), (14, 24, 54), (-6, -40, 50)):
            line(p, (hx, sd * 10), ((hx + fx) / 2 + 4, sd * (fy * 0.9)), 6, pal["leg"][0])
            line(p, ((hx + fx) / 2 + 4, sd * (fy * 0.9)), (fx, sd * fy), 5, pal["leg"][0])
        line(p, (54, sd * 3), (96, sd * 40), 3, pal["leg"][0])
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(pal["wing"][0])
    p.drawEllipse(QPointF(-14, 0), 46, 22)
    p.setBrush(pal["wing"][1])
    p.drawEllipse(QPointF(-14, 0), 40, 17)
    p.setBrush(pal["ring"][0])
    p.drawEllipse(QPointF(31, 0), 19, 16)
    p.setBrush(pal["inner"][0])
    p.drawEllipse(QPointF(31, 0), 13, 11)
    p.end()
    return QIcon(pm)


# ----------------------------------------------------------------------------
# gestor: cuándo y por dónde aparecen
# ----------------------------------------------------------------------------
class Manager:
    def __init__(self, app, settings):
        self.app = app
        self.cfg = settings
        self.bugs = []
        self.next_id = 0
        self.clock = QElapsedTimer()
        self.tick_timer = QTimer()
        self.tick_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.tick_timer.setInterval(16)
        self.tick_timer.timeout.connect(self.tick)
        self.next_timer = QTimer()
        self.next_timer.setSingleShot(True)
        self.next_timer.timeout.connect(self.on_random)

    def get(self, key, default):
        return self.cfg.value(key, default)

    def schedule(self, first=False):
        _, lo, hi = FREQS.get(self.get("freq", "media"), FREQS["media"])
        delay = random.uniform(6, 12) if first else random.uniform(lo, hi)
        self.next_timer.start(int(delay * 1000))

    def on_random(self):
        n = 1 if random.random() > 0.12 else random.randint(2, 3)
        for i in range(n):
            QTimer.singleShot(int(i * random.uniform(500, 1600)), self.spawn)
        self.schedule()

    @staticmethod
    def factor_at(x, y):
        """Densidad del monitor (144 dpi = 1.5): para que el bicho tenga el mismo tamaño REAL en todos."""
        pt = QPoint(int(x), int(y))
        scr = QGuiApplication.screenAt(pt)
        if scr is None:  # fuera de toda pantalla: la más cercana
            best, bd = None, 1e18
            for sc in QGuiApplication.screens():
                r = sc.geometry()
                dx, dy = max(r.left() - x, 0, x - r.right()), max(r.top() - y, 0, y - r.bottom())
                if dx * dx + dy * dy < bd:
                    best, bd = sc, dx * dx + dy * dy
            scr = best
        return clamp(scr.logicalDotsPerInch() / 96.0, 0.75, 3.0) if scr else 1.0

    def spawn(self, kind=None, screen=None, ltr=None, vertical=False):
        kind = kind or self.get("kind", "azar")
        if kind == "azar":
            kind = random.choice(("cucaracha", "arana"))
        spec = ROACH if kind == "cucaracha" else SPIDER
        variant = random.randrange(len(SPRITES["cucaracha" if spec is ROACH else "arana"]) or 3)
        size = SIZES.get(self.get("size", "medio"), SIZES["medio"])[1]
        s_base = size * random.uniform(0.85, 1.15) * (0.82 if (spec is ROACH and variant == 2) else 1.0)

        screens = QGuiApplication.screens()
        scr = screen or random.choice(screens)
        fmax = max(clamp(sc.logicalDotsPerInch() / 96.0, 0.75, 3.0) for sc in screens)
        m = 190 * s_base * fmax
        horizontal = ltr is not None or (not vertical and random.random() < 0.75)
        if horizontal:
            # cruza TODO el escritorio (todos los monitores): entra por el borde exterior y sale por el otro
            if ltr is None:
                ltr = random.random() < 0.5
            left_scr = min(screens, key=lambda q: q.geometry().left())
            right_scr = max(screens, key=lambda q: q.geometry().right())
            gi = (left_scr if ltr else right_scr).geometry()
            go = (right_scr if ltr else left_scr).geometry()
            y0 = random.uniform(gi.top() + gi.height() * 0.1, gi.bottom() - gi.height() * 0.1)
            y1 = clamp(y0 + random.uniform(-go.height() * 0.45, go.height() * 0.45), go.top() + 20, go.bottom() - 20)
            start = (gi.left() - m if ltr else gi.right() + m, y0)
            target = (go.right() + m if ltr else go.left() - m, y1)
        else:
            g = scr.geometry()
            ttb = random.random() < 0.5
            x0 = random.uniform(g.left() + g.width() * 0.1, g.right() - g.width() * 0.1)
            x1 = clamp(x0 + random.uniform(-g.width() * 0.3, g.width() * 0.3), g.left() + 20, g.right() - 20)
            start = (x0, g.top() - m if ttb else g.bottom() + m)
            target = (x1, g.bottom() + m if ttb else g.top() - m)

        try:
            s = s_base * self.factor_at(*start)
            c = Creature(spec, s, start, target, variant)
            c.s_base = s_base
            w = BugWindow(c, s_base * fmax)
            self.next_id += 1
            w.bid = self.next_id
            w.last_scr, w.last_beat = None, 0.0
            LOG.info("SPAWN bicho#%d %s variante=%d escala=%.2f en pantalla [%s] inicio=(%.0f,%.0f) destino=(%.0f,%.0f) ventana=%dpx",
                     w.bid, spec.name, variant, s, screen_id(scr), start[0], start[1], target[0], target[1], w.side)
            w.show()
            self.bugs.append(w)
            if not self.tick_timer.isActive():
                self.clock.restart()
                self.tick_timer.start()
        except Exception:
            LOG.exception("No pude crear el bicho")

    def _watch(self, w, now):
        """Deja en el log en qué pantalla está cada ventana (al cambiar) y un latido por segundo."""
        scr = w.screen()
        name = screen_id(scr) if scr else "?"
        if name != w.last_scr:
            LOG.info("bicho#%d: su ventana pasó a la pantalla [%s] pos=(%d,%d) tam=%dx%d dpr=%.2f", w.bid, name,
                     w.ox, w.oy, w.width(), w.height(), w.devicePixelRatioF())
            w.last_scr = name
        if now - w.last_beat >= 1.0:
            w.last_beat = now
            LOG.debug("bicho#%d %s centro=(%.0f,%.0f) v=%.0f estado=%s pantalla=[%s]", w.bid, w.c.spec.name,
                      w.c.x, w.c.y, w.c.v, w.c.state, name)

    def tick(self):
        dt = min(self.clock.restart() / 1000.0, 0.05)
        pos = QCursor.pos()
        cur = (pos.x(), pos.y())
        flee = str(self.get("flee", "true")).lower() == "true"
        now = time.monotonic()
        alive = []
        for w in self.bugs:
            try:
                w.c.s_goal = w.c.s_base * self.factor_at(w.c.x, w.c.y)
                w.step(dt, cur, flee)
                self._watch(w, now)
            except Exception:
                LOG.exception("Error en bicho#%d; lo saco de pantalla", w.bid)
                w.c.dead = True
            if w.c.dead:
                LOG.info("FIN bicho#%d tras %.1fs, última posición=(%.0f,%.0f)", w.bid, w.c.age, w.c.x, w.c.y)
                w.hide()
                w.deleteLater()
            else:
                alive.append(w)
        self.bugs = alive
        if not self.bugs:
            self.tick_timer.stop()


def build_tray(app, mgr):
    tray = QSystemTrayIcon(tray_icon(), app)
    tray.setToolTip("Bichos en pantalla")
    menu = QMenu()
    a = menu.addAction("Soltar uno ahora")
    a.triggered.connect(lambda: mgr.spawn())
    a = menu.addAction("Soltar una cucaracha")
    a.triggered.connect(lambda: mgr.spawn("cucaracha"))
    a = menu.addAction("Soltar una araña")
    a.triggered.connect(lambda: mgr.spawn("arana"))
    menu.addSeparator()

    def radio(title, options, key, default, on_change=None):
        sub = menu.addMenu(title)
        grp = QActionGroup(sub)
        grp.setExclusive(True)
        cur = str(mgr.get(key, default))
        for k, label in options.items():
            act = QAction(label, sub)
            act.setCheckable(True)
            act.setChecked(k == cur)
            grp.addAction(act)
            sub.addAction(act)

            def chosen(_, k=k):
                mgr.cfg.setValue(key, k)
                mgr.cfg.sync()
                if on_change:
                    on_change()
            act.triggered.connect(chosen)

    radio("Frecuencia", {k: v[0] for k, v in FREQS.items()}, "freq", "media", lambda: mgr.schedule())
    radio("Insecto", KINDS, "kind", "azar")
    radio("Tamaño", {k: v[0] for k, v in SIZES.items()}, "size", "medio")

    flee = menu.addAction("Se asusta del mouse")
    flee.setCheckable(True)
    flee.setChecked(str(mgr.get("flee", "true")).lower() == "true")
    flee.toggled.connect(lambda on: (mgr.cfg.setValue("flee", "true" if on else "false"), mgr.cfg.sync()))

    if AUTOSTART:  # solo en desarrollo: el .exe no escribe en el registro de Windows
        st = menu.addAction("Iniciar con Windows")
        st.setCheckable(True)
        st.setChecked(startup_enabled())
        st.toggled.connect(set_startup)

    menu.addSeparator()
    menu.addAction("Ver registro (log)").triggered.connect(lambda: os.startfile(LOG_PATH))
    menu.addAction("Salir").triggered.connect(
        lambda: (LOG.info("Saliendo: se eligió 'Salir' en el menú de la bandeja"), app.quit()))
    tray.setContextMenu(menu)
    tray.show()
    return tray, menu


DEV_FLAGS = ("--png", "--test", "--probar-pantallas", "--debug")


def main():
    dev = None
    if not FROZEN and any(a in sys.argv for a in DEV_FLAGS):
        import devtools  # herramientas de desarrollo (capturas, pruebas): NO existen dentro del .exe
        devtools.attach(sys.modules[__name__])
        dev = devtools
    if dev and "--png" in sys.argv:
        out = sys.argv[sys.argv.index("--png") + 1]
        esc = float(sys.argv[sys.argv.index("--esc") + 1]) if "--esc" in sys.argv else 1.5
        solo = int(sys.argv[sys.argv.index("--solo") + 1]) if "--solo" in sys.argv else None
        dev.render_preview(out, scale=esc, pose="quieta" if "--quieta" in sys.argv else "run", solo=solo)
        return
    if dev and "--debug" in sys.argv:  # mensajes detallados de la capa de ventanas de Qt, también al log
        os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=true")
    setup_logging()
    if FROZEN:
        # el .exe ignora cualquier variable QT_* del entorno (rutas de plugins, temas, depuración):
        # solo carga los plugins que trae empaquetados, nadie puede inyectar otros desde afuera
        for k in [k for k in os.environ if k.upper().startswith("QT_")]:
            del os.environ[k]
        os.environ["QT_PLUGIN_PATH"] = os.path.join(RES_DIR, "PyQt6", "Qt6", "plugins")
        os.environ["QT_QPA_PLATFORM"] = "windows"
    # Monitores con escalas distintas (100 % / 150 %): con el escalado automático de Qt la ventana del
    # bicho se reescala al cruzar de un monitor a otro, en bucle, hasta pedir un bitmap gigante y Qt
    # aborta. Trabajando en píxeles reales no hay reescalado y el escritorio es un solo espacio continuo.
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.aboutToQuit.connect(lambda: LOG.info("aboutToQuit (la aplicación está por cerrar)"))
    app.lastWindowClosed.connect(lambda: LOG.debug("se cerró la última ventana (no cierra la app)"))
    lock = QLockFile(os.path.join(TEMP_DIR, "bichos_pantalla%s.lock" % ("_exe" if FROZEN else "")))
    lock.setStaleLockTime(0)
    testing = bool(dev) and ("--test" in sys.argv or "--probar-pantallas" in sys.argv)
    if not testing and not lock.tryLock(100):
        LOG.info("Ya hay otra copia corriendo; esta se cierra")
        return  # ya hay uno corriendo
    begin_session()
    LOG.info("Plataforma de Qt: %s", app.platformName())
    log_screens(app)
    load_sprites()
    cfg = QSettings(os.path.join(DATA_DIR, "bichos.ini"), QSettings.Format.IniFormat)
    mgr = Manager(app, cfg)
    tray, menu = build_tray(app, mgr)  # noqa: F841 (hay que mantenerlos vivos)
    if dev and "--test" in sys.argv:
        dev.run_test(app, mgr)
    elif dev and "--probar-pantallas" in sys.argv:
        dev.run_screens_test(app, mgr)
    else:
        mgr.schedule(first=True)
        if "--ya" in sys.argv:
            QTimer.singleShot(400, mgr.spawn)
        tray.showMessage("Bichos en pantalla", "Activo. Botón derecho en el icono para configurar.",
                         QSystemTrayIcon.MessageIcon.Information, 3500)
    code = app.exec()
    lock.unlock()
    sys.exit(code)


if __name__ == "__main__":
    main()
