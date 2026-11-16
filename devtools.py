# -*- coding: utf-8 -*-
"""
Herramientas de DESARROLLO de bichos.py. NO se empaquetan en el .exe (por seguridad: aquí hay
capturas de pantalla y pruebas que no deben existir en el programa que se reparte).

  python bichos.py --png salida.png [--solo N --esc 3] [--quieta]   hoja de prueba sin ventanas
  python bichos.py --test                                          ventanas reales + capturas (usa la pantalla)
  python bichos.py --probar-pantallas                              cruza todos los monitores
  python bichos.py --debug                                         mensajes detallados de Qt en el log
"""


def attach(B):
    """Toma prestados todos los nombres de bichos.py (el módulo principal)."""
    globals().update({k: v for k, v in vars(B).items() if not k.startswith("__")})


def render_preview(path, scale=1.5, pose="run", solo=None):
    app = QGuiApplication(sys.argv)  # noqa: F841
    load_sprites()
    cells = [(ROACH, v) for v in range(3)] + [(SPIDER, v) for v in range(3)]
    if solo is not None:
        cells = [cells[solo]]
    cols = 1 if solo is not None else 3
    rows = 1 if solo is not None else 2
    side = int(2 * 185 * scale)
    img = QImage(side * cols, side * rows, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Q(210, 214, 218))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    for i, (spec, v) in enumerate(cells):
        heading = 0.35 + 0.5 * (i % 3)
        far = (math.cos(heading) * 1e5, math.sin(heading) * 1e5)
        speed = (0.55 if pose == "run" else 0.0) * spec.vmax * scale
        c = Creature(spec, scale, (0, 0), far, v, debug_speed=speed if pose == "run" else None)
        if pose != "run":  # pose quieta: caminar un poco y frenar
            c.debug = 0.5 * spec.vmax * scale
            for _ in range(70):
                c.update(1 / 60.0)
            c.debug = 0.0
            for _ in range(40):
                c.update(1 / 60.0)
        else:
            for _ in range(110 + i * 7):
                c.update(1 / 60.0)
        sh = QImage(int(side * SHADOW_K) + 1, int(side * SHADOW_K) + 1, QImage.Format.Format_ARGB32_Premultiplied)
        p.save()
        p.translate((i % cols) * side, (i // cols) * side)
        p.setClipRect(QRectF(0, 0, side, side))
        c.paint(p, c.x - side / 2, c.y - side / 2, side, sh)
        p.restore()
    p.end()
    img.save(path)
    print("OK", path, img.width(), img.height())


def run_test(app, mgr):
    """Suelta uno, deja correr ~2 s, guarda capturas de las ventanas y sale."""
    mgr.spawn("cucaracha")
    mgr.spawn("arana")
    scr = QGuiApplication.screens()
    for i, w in enumerate(mgr.bugs):  # uno en el centro de cada monitor, corriendo hacia la derecha
        g = scr[i % len(scr)].geometry()
        w.c.x, w.c.y = g.center().x(), g.center().y()
        w.c.target = (g.right() + 400, g.center().y())
        w.c.a = 0.0
        w.c.state, w.c.timer, w.c.vt = "run", 5.0, 200 * w.c.s

    def snap():
        import ctypes
        for i, w in enumerate(mgr.bugs):
            w.grab().save(os.path.join(DATA_DIR, "_test_widget_%d.png" % i))
            s_ = QGuiApplication.screenAt(QPoint(int(w.c.x), int(w.c.y)))
            g = s_.geometry()
            sd = int(w.c.spec.R * 2 * w.c.s)  # recorte justo alrededor del bicho
            pm = s_.grabWindow(0, int(w.c.x - g.x() - sd / 2), int(w.c.y - g.y() - sd / 2), sd, sd)
            pm.scaledToWidth(560, Qt.TransformationMode.SmoothTransformation).save(
                os.path.join(DATA_DIR, "_test_pantalla_%d.png" % i))
            LOG.info("test: bicho %d en [%s] dpi=%.0f escala_actual=%.2f", i, s_.name(), s_.logicalDotsPerInch(), w.c.s)
            ex = ctypes.windll.user32.GetWindowLongW(int(w.winId()), -20)
            print("ventana %d  WS_EX_TRANSPARENT=%s  TOPMOST=%s  TOOLWINDOW=%s  NOACTIVATE=%s" % (
                i, bool(ex & 0x20), bool(ex & 0x8), bool(ex & 0x80), bool(ex & 0x08000000)))
        print("ventanas vivas:", len(mgr.bugs))
        app.quit()
    QTimer.singleShot(1300, snap)


def run_screens_test(app, mgr):
    """Cruza CADA pantalla de punta a punta, en los dos sentidos, y espera a que terminen.
    Sirve para reproducir problemas con varios monitores (el resultado queda en bichos.log)."""
    for ltr in (True, False):                       # de punta a punta del escritorio, ida y vuelta
        mgr.spawn("cucaracha", ltr=ltr)
        mgr.spawn("arana", ltr=ltr)
    for s in app.screens():                         # y en vertical por cada monitor
        mgr.spawn("cucaracha", screen=s, vertical=True)
    timer = QTimer()
    timer.timeout.connect(lambda: (LOG.info("Prueba de pantallas: terminó sin cierres"), app.quit())
                          if not mgr.bugs else None)
    timer.start(500)
    mgr._test_timer = timer
    QTimer.singleShot(120000, lambda: (LOG.info("Saliendo: tiempo máximo de la prueba"), app.quit()))


