# -*- coding: utf-8 -*-
"""Genera bichos.ico (icono del .exe) renderizando la cucaracha real vista desde arriba."""
import math
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, ".."))
sys.path.insert(0, RAIZ)

from PyQt6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PIL import Image  # noqa: E402

import bichos  # noqa: E402

app = QGuiApplication(sys.argv)
bichos.load_sprites()

esc = 1.0
c = bichos.Creature(bichos.ROACH, esc, (0, 0), (0, -1e5), 0, debug_speed=0.5 * bichos.ROACH.vmax)
for _ in range(80):
    c.update(1 / 60.0)
side = int(2 * bichos.ROACH.R * esc)
img = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
img.fill(0)
p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
sh = QImage(int(side * bichos.SHADOW_K) + 1, int(side * bichos.SHADOW_K) + 1, QImage.Format.Format_ARGB32_Premultiplied)
c.paint(p, c.x - side / 2, c.y - side / 2, side, sh)
p.end()
tmp = os.path.join(AQUI, "_icono_tmp.png")
img.save(tmp)

im = Image.open(tmp).convert("RGBA")
box = im.getchannel("A").point(lambda v: 255 if v > 30 else 0).getbbox()
im = im.crop(box)
lado = int(max(im.size) * 1.08)
lienzo = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
lienzo.paste(im, ((lado - im.width) // 2, (lado - im.height) // 2), im)
lienzo = lienzo.resize((256, 256), Image.LANCZOS)
salida = os.path.join(RAIZ, "bichos.ico")
lienzo.save(salida, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
os.remove(tmp)
print("icono:", salida)
