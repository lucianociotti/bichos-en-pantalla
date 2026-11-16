# -*- coding: utf-8 -*-
"""
Convierte una FOTO de un insecto vista desde arriba en un "cuerpo" con fondo transparente
para usar en bichos.py (las patas y antenas siguen siendo animadas encima).

Qué hace:
  1. Recorta franjas negras con texto del pie (típicas de fotos de museo/Wikimedia).
  2. Saca el fondo claro/liso.
  3. Quita patas y antenas (apertura morfológica) y se queda con el cuerpo.
  4. Endereza el cuerpo (eje largo horizontal, cabeza a la derecha).
  5. Limpia el borde (sin halo blanco) y guarda PNG con transparencia.
  6. Genera 3 variantes de color (original, oscura, clara) y mide la paleta de las patas.

Uso:
  python preparar_foto.py FOTO.jpg --tipo cucaracha            -> sprites/cucaracha_v0..v2.png + cucaracha.json
  python preparar_foto.py FOTO.jpg --tipo arana --nombre arana1
Opciones:
  --invertir        gira 180° (si la cabeza quedó a la izquierda)
  --abrir 0.5       qué tan grueso es lo que se conserva (fracción del ancho máximo); subir = quita más
  --fondo-sat 45    umbral de saturación para distinguir insecto de fondo (bajar si el insecto es muy pálido)
  --vista           además guarda una hoja de vista previa (_vista.png)
  --elipses "cx,cy,rx,ry[,grados];..."  arañas: cuerpo a mano (1ª = cefalotórax/cabeza, última = abdomen)
  --femur / --pata "bx,by,tx,ty,ancho"  recorta un tramo de pata real (base, punta, ancho de la banda)
  --debug ARCHIVO   guarda la foto con el contorno del cuerpo (rojo) y los tramos de pata (verde/azul)
Las coordenadas son píxeles de la foto original; se leen mirando la foto con una grilla.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def disk(r):
    r = max(1, int(round(r)))
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r


def rellenar_huecos_chicos(mask, max_area):
    """Rellena solo huecos pequeños (brillos, poros). Los grandes (aire entre pata y cuerpo) se respetan."""
    lab, n = ndi.label(~mask)
    if n == 0:
        return mask
    areas = ndi.sum(~mask, lab, range(1, n + 1))
    borde = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])).tolist())
    out = mask.copy()
    for i, ar in enumerate(areas, start=1):
        if i not in borde and ar <= max_area:
            out[lab == i] = True
    return out


def quitar_franja(a):
    """Recorta la franja de texto del pie: sube desde abajo hasta la primera fila claramente blanca."""
    h = a.shape[0]
    medias = a.mean(axis=(1, 2))
    for y in range(h - 1, h // 2, -1):
        if medias[y] > 215:
            return a[:y + 1]
    return a


def mascara_fondo(rgb_img, sat_min, val_max):
    hsv = np.asarray(rgb_img.convert("HSV")).astype(np.int32)
    s, v = hsv[..., 1], hsv[..., 2]
    return (s > sat_min) | (v < val_max)


def lum(c):
    return 0.299 * c[..., 0] + 0.587 * c[..., 1] + 0.114 * c[..., 2]


def grade(arr, kind):
    """Variantes de color sobre un array float RGB 0..255 (sirve también para 3 colores sueltos)."""
    a = arr.astype(np.float32)
    if kind == 0:
        return np.clip(a, 0, 255)
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8).reshape((-1, 1, 3)) if a.ndim == 2 else
                         np.clip(a, 0, 255).astype(np.uint8), "RGB")
    hsv = np.asarray(im.convert("HSV")).astype(np.float32)
    if kind == 1:    # oscura: caoba casi negra
        hsv[..., 2] *= 0.55
        hsv[..., 1] = np.clip(hsv[..., 1] * 0.95, 0, 255)
    else:            # clara: más joven, tostada
        hsv[..., 0] = np.clip(hsv[..., 0] + 4, 0, 255)
        hsv[..., 1] = np.clip(hsv[..., 1] * 0.78, 0, 255)
        hsv[..., 2] = np.clip(hsv[..., 2] * 1.32 + 10, 0, 255)
    out = np.asarray(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")).astype(np.float32)
    return out.reshape(arr.shape) if arr.ndim == 2 else out


def extraer_franja(im, alfa, spec, args, excluir=None, tope=560):
    """Recorta de la foto un tramo de pata ("bx,by,tx,ty,ancho": base, punta y ancho de la banda, en píxeles
    de la foto) y lo endereza: queda horizontal, con la base a la izquierda, sobre fondo transparente."""
    bx, by, tx, ty, W = [float(t) for t in spec.split(",")]
    dx, dy = tx - bx, ty - by
    L = float(np.hypot(dx, dy))
    phi = float(np.degrees(np.arctan2(dy, dx)))
    pad = 0.04 * L
    box = (int(round(bx - pad)), int(round(by - W / 2)), int(round(bx + L + pad)), int(round(by + W / 2)))
    rot = im.rotate(phi, resample=Image.BICUBIC, center=(bx, by), fillcolor=(255, 255, 255))
    crop = rot.crop(box)
    if alfa is not None:
        ra = alfa.rotate(phi, resample=Image.BICUBIC, center=(bx, by), fillcolor=0)
        m = np.asarray(ra.crop(box)) > 127
    else:
        m = mascara_fondo(crop, args.fondo_sat, args.fondo_val)
    if excluir is not None:  # sacar el cuerpo (ya detectado) para que no se cuele en la tira
        re = excluir.rotate(phi, resample=Image.BILINEAR, center=(bx, by), fillcolor=0)
        m &= ~(np.asarray(re.crop(box)) > 127)
    m = ndi.binary_opening(m, structure=disk(1))
    lab, n = ndi.label(m)
    if n == 0:
        sys.exit("No encontré la pata en %s: revisá las coordenadas" % spec)
    cy = m.shape[0] // 2
    banda = np.zeros_like(m)
    banda[max(0, cy - int(W * 0.15)):cy + int(W * 0.15) + 1, :] = True
    cuentas = ndi.sum(m & banda, lab, range(1, n + 1))
    m = lab == (1 + int(np.argmax(cuentas)))                 # la pata (no las vecinas que se cuelan)
    m = rellenar_huecos_chicos(m, 0.002 * m.size)
    inner = ndi.binary_erosion(m, structure=disk(2))
    if inner.sum() < 10:
        inner = m
    idx = ndi.distance_transform_edt(~inner, return_distances=False, return_indices=True)
    rgb = np.asarray(crop).astype(np.float32)
    rgb = rgb[idx[0], idx[1]]
    rgb[inner] = np.asarray(crop).astype(np.float32)[inner]
    al = np.clip((ndi.gaussian_filter(m.astype(np.float32), 0.9) - 0.4) * 2.2, 0, 1)
    spr = Image.fromarray(np.dstack([rgb, al * 255]).astype(np.uint8), "RGBA")
    pad_px = int(round(bx - box[0]))
    base_cols = (al[:, pad_px:pad_px + max(3, int(0.12 * L))] > 0.5).sum(axis=0)
    t0 = float(np.median(base_cols[base_cols > 0])) if (base_cols > 0).any() else float(W * 0.3)
    k = min(1.0, tope / spr.width)
    if k < 1.0:
        spr = spr.resize((int(round(spr.width * k)), int(round(spr.height * k))), Image.LANCZOS)
    return spr, {"largo": L * k, "pad": pad_px * k, "alto": spr.height, "grosor": max(1.0, t0 * k)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("foto")
    ap.add_argument("--tipo", choices=("cucaracha", "arana"), required=True)
    ap.add_argument("--nombre", default=None)
    ap.add_argument("--salida", default=None, help="carpeta de salida (por defecto ../sprites)")
    ap.add_argument("--invertir", action="store_true")
    ap.add_argument("--abrir", type=float, default=0.5)
    ap.add_argument("--fondo-sat", type=int, default=45)
    ap.add_argument("--fondo-val", type=int, default=140)
    ap.add_argument("--ancho", type=int, default=720, help="ancho final del sprite en píxeles")
    ap.add_argument("--regrow", type=float, default=None, help="cuánto se recupera hacia afuera tras quitar patas")
    ap.add_argument("--sin-elipses", action="store_true", help="arañas: no ajustar elipses (usar el recorte tal cual)")
    ap.add_argument("--debug", default=None, help="guardar acá una imagen con el contorno elegido sobre la foto")
    ap.add_argument("--femur", default=None, help='tramo de pata cerca del cuerpo: "bx,by,tx,ty,ancho" (base, rodilla)')
    ap.add_argument("--pata", default=None, help='resto de la pata: "bx,by,tx,ty,ancho" (rodilla, punta)')
    ap.add_argument("--elipses", default=None,
                    help='arañas: cuerpo a mano, "cx,cy,rx,ry[,grados];..." en píxeles de la foto (cefalotórax y abdomen)')
    ap.add_argument("--elipse-k", type=float, default=1.0, help="arañas: escala de las elipses (1.0 = tamaño medido)")
    ap.add_argument("--variantes", type=int, default=None, help="cuántas variantes de color (cucaracha 3, araña 1)")
    ap.add_argument("--vista", action="store_true")
    args = ap.parse_args()

    nombre = args.nombre or args.tipo
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = args.salida or os.path.join(here, "..", "sprites")
    os.makedirs(out_dir, exist_ok=True)

    im = Image.open(args.foto)
    im.load()
    tiene_alfa = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    alfa0 = None
    if tiene_alfa:
        rgba0 = im.convert("RGBA")
        a0 = np.asarray(rgba0.getchannel("A"))
        if a0.min() < 128 and (a0 < 128).mean() > 0.02:   # trae fondo transparente de verdad
            alfa0 = rgba0.getchannel("A")
            im = Image.merge("RGB", rgba0.split()[:3])
            print("la imagen ya trae fondo transparente: uso ese canal como máscara")
    if alfa0 is None:
        im = im.convert("RGB")
        im = Image.fromarray(quitar_franja(np.asarray(im)))

    # trabajar a ~1600 px para que sea rápido (nunca agrandar)
    f = min(1.0, 1600.0 / max(im.size))
    tam = (max(1, int(im.width * f)), max(1, int(im.height * f)))
    w = im.resize(tam, Image.LANCZOS)
    rgb = np.asarray(w).astype(np.float32)

    if alfa0 is not None:
        fg = np.asarray(alfa0.resize(tam, Image.LANCZOS)) > 127
    else:
        fg = mascara_fondo(w, args.fondo_sat, args.fondo_val)
    fg = rellenar_huecos_chicos(ndi.binary_opening(fg, structure=disk(2)), 0.002 * fg.size)
    lab, n = ndi.label(fg)
    if n == 0:
        sys.exit("No encontré ningún insecto: probá bajar --fondo-sat")
    sizes = ndi.sum(fg, lab, range(1, n + 1))
    fg = lab == (1 + int(np.argmax(sizes)))          # solo el bicho más grande

    # cuerpo = apertura grande (saca patas/antenas) + un poco de regrowth para recuperar puntas y la cintura
    dt = ndi.distance_transform_edt(fg)
    r_open = max(3.0, args.abrir * dt.max())
    core = ndi.binary_opening(fg, structure=disk(r_open))
    lab, n = ndi.label(core)
    if n == 0:
        sys.exit("--abrir es demasiado alto para este bicho: probá un valor menor")
    sizes = ndi.sum(core, lab, range(1, n + 1))
    keep = [i + 1 for i, s in enumerate(sizes) if s >= 0.06 * sizes.max()]   # cefalotórax y abdomen quedan separados
    core = np.isin(lab, keep)
    regrow = args.regrow if args.regrow is not None else (0.10 if args.tipo == "cucaracha" else 0.12)
    if args.tipo == "arana" and args.elipses:
        # elipses indicadas a mano (en píxeles de la foto original): "cx,cy,rx,ry[,grados];cx,cy,rx,ry[,grados]"
        body = np.zeros_like(fg)
        yy, xx = np.mgrid[0:fg.shape[0], 0:fg.shape[1]]
        for parte in args.elipses.split(";"):
            v = [float(t) for t in parte.split(",")]
            cx, cy, rx, ry = (v[0] * f, v[1] * f, v[2] * f, v[3] * f)
            ang = np.radians(v[4]) if len(v) > 4 else 0.0
            dx, dy = xx - cx, yy - cy
            u = dx * np.cos(ang) + dy * np.sin(ang)
            w_ = -dx * np.sin(ang) + dy * np.cos(ang)
            body |= (u / rx) ** 2 + (w_ / ry) ** 2 <= 1.0
        # la cintura (pedicelo) es fina: puentearla; y recortar con la silueta real (puntas del abdomen)
        L = max(body.shape) * 0.0
        ys_, xs_ = np.nonzero(body)
        L = max(xs_.max() - xs_.min(), ys_.max() - ys_.min())
        body = ndi.binary_closing(body, structure=disk(0.10 * L)) & ndi.binary_dilation(fg, structure=disk(1))
        body = rellenar_huecos_chicos(body, 0.002 * fg.size)
    elif args.tipo == "arana" and not args.sin_elipses:
        # las bases de las patas se funden con el cuerpo: reemplazo cada parte (cefalotórax, abdomen)
        # por la elipse que mejor la representa; es justo su forma natural
        body = np.zeros_like(fg)
        yy, xx = np.mgrid[0:fg.shape[0], 0:fg.shape[1]]
        lab_c, _ = ndi.label(core)
        for i in range(1, lab_c.max() + 1):
            ys, xs = np.nonzero(lab_c == i)
            if len(xs) < 50:
                continue
            cx, cy = xs.mean(), ys.mean()
            ev, evec = np.linalg.eigh(np.cov(np.vstack([xs - cx, ys - cy])))
            a, b = 2.0 * args.elipse_k * np.sqrt(ev[1]), 2.0 * args.elipse_k * np.sqrt(ev[0])
            ux, uy = evec[:, 1]
            dx, dy = xx - cx, yy - cy
            body |= ((dx * ux + dy * uy) / a) ** 2 + ((-dx * uy + dy * ux) / b) ** 2 <= 1.0
        body = ndi.binary_closing(body, structure=disk(0.25 * dt.max()))   # une cefalotórax y abdomen por la cintura
    else:
        body = ndi.binary_dilation(core, structure=disk(regrow * dt.max())) & fg
        body = rellenar_huecos_chicos(body, 0.002 * fg.size)
        # podar muñones: una apertura más suave sobre el resultado quita lo que quedó de las patas
        body = ndi.binary_opening(body, structure=disk(max(2.0, 0.22 * dt.max()))) | core
    lab, n = ndi.label(body)
    if n > 1:
        sizes = ndi.sum(body, lab, range(1, n + 1))
        body = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= 0.06 * sizes.max()])

    if args.debug:  # contorno del cuerpo elegido, dibujado sobre la foto, para ajustar parámetros mirando
        from PIL import ImageDraw
        borde = body & ~ndi.binary_erosion(body, structure=disk(2))
        dbg = rgb.copy()
        dbg[~fg] = dbg[~fg] * 0.35 + 255 * 0.65
        dbg[borde] = (255, 0, 0)
        dimg = Image.fromarray(dbg.astype(np.uint8))
        dd = ImageDraw.Draw(dimg)
        for spec_, col_ in ((args.femur, (0, 160, 0)), (args.pata, (0, 90, 255))):
            if spec_:
                bx_, by_, tx_, ty_, W_ = [float(t) for t in spec_.split(",")]
                a_ = np.arctan2(ty_ - by_, tx_ - bx_)
                nx_, ny_ = -np.sin(a_) * W_ / 2, np.cos(a_) * W_ / 2
                pts_ = [((bx_ + nx_) * f, (by_ + ny_) * f), ((tx_ + nx_) * f, (ty_ + ny_) * f),
                        ((tx_ - nx_) * f, (ty_ - ny_) * f), ((bx_ - nx_) * f, (by_ - ny_) * f)]
                dd.polygon(pts_, outline=col_)
        dimg.save(args.debug)
        print("depuración:", args.debug)

    # paleta de las patas: lo que es insecto pero NO cuerpo
    legs = fg & ~ndi.binary_dilation(body, structure=disk(0.12 * dt.max()))
    legs = ndi.binary_opening(legs, structure=disk(1))
    pal = None
    if legs.sum() > 200:
        px = rgb[legs]
        L = lum(px)
        qs = np.percentile(L, [18, 82])
        dark = px[L <= qs[0]].mean(axis=0)
        mid = np.median(px, axis=0)
        light = px[L >= qs[1]].mean(axis=0)
        pal = np.stack([dark, mid, light])
    else:
        print("aviso: casi no hay patas en la foto; se usarán colores del cuerpo", file=sys.stderr)
        px = rgb[body]
        L = lum(px)
        pal = np.stack([px[L <= np.percentile(L, 15)].mean(axis=0), np.median(px, axis=0),
                        px[L >= np.percentile(L, 85)].mean(axis=0)])

    # color de borde sin halo blanco: lo que quedó fuera del núcleo toma el color del interior más cercano
    inner = ndi.binary_erosion(body, structure=disk(3))
    idx = ndi.distance_transform_edt(~inner, return_distances=False, return_indices=True)
    rgb_clean = rgb[idx[0], idx[1]]
    rgb_clean[inner] = rgb[inner]

    alpha = ndi.gaussian_filter(body.astype(np.float32), 1.3)
    alpha = np.clip((alpha - 0.42) * 2.4, 0, 1)    # borde nítido pero sin escalones

    rgba = np.dstack([rgb_clean, alpha * 255]).astype(np.uint8)
    spr = Image.fromarray(rgba, "RGBA")

    # enderezar: eje largo (PCA) horizontal
    if args.tipo == "arana" and args.elipses:
        # con elipses indicadas: la primera es la cabeza (cefalotórax) y la última el abdomen
        partes = [[float(t) for t in p.split(",")] for p in args.elipses.split(";")]
        vx, vy = partes[0][0] - partes[-1][0], partes[0][1] - partes[-1][1]
        phi = np.degrees(np.arctan2(vy, vx))
        spr = spr.rotate(phi, resample=Image.BICUBIC, expand=True)   # la cabeza queda a la derecha
    else:
        ys, xs = np.nonzero(body)
        cov = np.cov(np.vstack([xs - xs.mean(), ys - ys.mean()]))
        evals, evecs = np.linalg.eigh(cov)
        vx, vy = evecs[:, int(np.argmax(evals))]
        phi = np.degrees(np.arctan2(vy, vx))
        spr = spr.rotate(phi, resample=Image.BICUBIC, expand=True)
        if args.invertir:
            spr = spr.rotate(180, resample=Image.BICUBIC)
    bbox = spr.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    spr = spr.crop(bbox)

    k = min(1.0, args.ancho / spr.width)             # solo achicar: agrandar no agrega detalle
    if k < 1.0:
        spr = spr.resize((args.ancho, max(1, int(round(spr.height * k)))), Image.LANCZOS)
    print("cuerpo: %dx%d px (relación ancho/largo = %.2f)" % (spr.width, spr.height, spr.height / spr.width))

    meta = {"tipo": args.tipo, "ancho_px": spr.width, "alto_px": spr.height, "variantes": []}
    base = np.asarray(spr).astype(np.float32)
    vistas = []
    franjas = {}                                    # tramos de pata reales de la foto
    excl = Image.fromarray((ndi.binary_dilation(body, structure=disk(3)) * 255).astype(np.uint8)).resize(
        im.size, Image.BILINEAR)
    for nom_, spec_ in (("femur", args.femur), ("pata", args.pata)):
        if spec_:
            franjas[nom_] = extraer_franja(im, alfa0, spec_, args, excluir=excl)
            print("franja %s: %dx%d px, grosor en la base %.0f px" % (
                nom_, franjas[nom_][0].width, franjas[nom_][0].height, franjas[nom_][1]["grosor"]))
    nvar = args.variantes if args.variantes is not None else (3 if args.tipo == "cucaracha" else 1)
    for v in range(nvar):
        g = base.copy()
        g[..., :3] = grade(base[..., :3], v)
        out = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "RGBA")
        fn = "%s_v%d.png" % (nombre, v)
        out.save(os.path.join(out_dir, fn))
        pv = grade(pal.reshape(3, 1, 3), v).reshape(3, 3)
        entrada = {
            "png": fn,
            "leg": [[int(round(c)) for c in col] for col in pv],
            "spine": [int(round(c * 0.55)) for c in pv[0]],
            "edge": [int(round(c * 0.5)) for c in pv[0]],
        }
        for nom_, (img_, m_) in franjas.items():
            arr_ = np.asarray(img_).astype(np.float32)
            arr_[..., :3] = grade(arr_[..., :3], v)
            fn_ = "%s_v%d_%s.png" % (nombre, v, nom_)
            Image.fromarray(np.clip(arr_, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(out_dir, fn_))
            entrada[nom_] = dict(m_, png=fn_)
        meta["variantes"].append(entrada)
        vistas.append(out)
        print("guardado", os.path.normpath(os.path.join(out_dir, fn)))
    with open(os.path.join(out_dir, nombre + ".json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=1)

    if args.vista:
        W = sum(x.width for x in vistas) + 40
        H = max(x.height for x in vistas) + 20
        hoja = Image.new("RGB", (W, H), (205, 209, 214))
        x0 = 10
        for x in vistas:
            hoja.paste(x, (x0, 10), x)
            x0 += x.width + 10
        hoja.save(os.path.join(out_dir, nombre + "_vista.png"))
        print("vista previa:", os.path.normpath(os.path.join(out_dir, nombre + "_vista.png")))


if __name__ == "__main__":
    main()
