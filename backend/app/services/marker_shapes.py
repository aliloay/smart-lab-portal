"""
Asset-shaped QR markers (2026-10-27, owner: "the QR code itself must form the camera, door, robot, laptop, bin or
shield - not an icon pasted on a QR").

How it is built - genuine QR, nothing covers the code:
  1. the payload is encoded by the qrcode library (error correction H); its matrix is drawn module by module;
  2. the asset's SILHOUETTE is built from module-sized cells AROUND the code on the same grid (camera body and
     viewfinder, door frame and leaf, robot base + arm links + joints + gripper, laptop bezel + keyboard, bin, shield,
     server stack, thermometer, crate + NFC waves), so the whole marker reads as the object;
  3. features INSIDE the code (camera lens ring, door-leaf edge, robot joint ring ...) only RECOLOUR real modules in
     the category's dark accent - a dark module stays dark, a light one stays white, nothing is deleted or added;
  4. a white gap of GAP modules separates the code from the silhouette (the scanner's quiet zone); the silhouette
     texture is a light tint with a darker outline, so a binarising decoder reads it as background.
Every rendered marker is decoded back (OpenCV here; jsQR in tests/test_marker_shapes + e2e) - a design that does not
read back is replaced by the plain white-card QR (render_plain), never served broken.
"""
from __future__ import annotations

import functools
import io
from typing import Callable

import qrcode
from PIL import Image, ImageColor, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_H

NAVY = (11, 18, 32)
GAP = 3                       # white modules between the code and the silhouette (quiet zone for the scanner)
SS = 4                        # silhouette masks are drawn at 4x and averaged per cell
TINT = 0.45                   # silhouette texture: accent this far towards white (lighter = safer for decoders)
MOD_SHADE = 0.55              # code modules: accent this far towards navy (dark enough for any decoder)

# category -> (accent, label)
CATS = {
    "camera": ("#7c3aed", "CAMERA"), "door": ("#0f766e", "DOOR CONTROLLER"), "robot": ("#ea580c", "ROBOT"),
    "pc": ("#2563eb", "LAB PC"), "consumables": ("#b45309", "CONSUMABLES"), "security": ("#dc2626", "SECURITY"),
    "server": ("#7e22ce", "FACE SERVER"), "environment": ("#15803d", "ENVIRONMENT"), "reusable": ("#0e7490", "REUSABLE ITEMS"),
    "equipment": ("#0369a1", "EQUIPMENT"), "device": ("#475569", "DEVICE"),
}
TYPE_CAT = {"Entry camera": "camera", "Security camera": "security", "Robot": "robot",
            "Door controller (master ESP32)": "door", "Lab PC": "pc", "Face server": "server",
            "Environment node": "environment", "Sensor node": "environment", "Consumables bin node": "consumables",
            "Consumables bin": "consumables", "Reusable-items bin node": "reusable", "Reusable-bin item": "reusable"}


def category(item: dict) -> str:
    c = TYPE_CAT.get(item.get("type") or "")
    if c:
        return c
    name = (item.get("name") or "").lower()
    if "laptop" in name or name.startswith("pc"):
        return "pc"
    if "cam" in name:
        return "camera"
    if any(k in name for k in ("robot", "ur5", "fanuc")):
        return "robot"
    return "device" if item.get("kind") == "device" else "equipment"


def _mix(c, d, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(c, d))


def matrix(code: str) -> list[list[bool]]:
    qr = qrcode.QRCode(version=4, error_correction=ERROR_CORRECT_H, border=0)
    qr.add_data(code)
    qr.make(fit=True)
    return qr.get_matrix()


# ---------------------------------------------------------------------------------------------- layouts ---
# A layout gets the code size n and returns (W, H, qx, qy, draw_silhouette, draw_feature). Grid units = modules.
# draw_silhouette(d, s) draws the object (white = 255) on a mask at scale s; draw_feature(d, s, qx, qy) draws the
# in-code feature (recoloured modules). Both may leave the code area alone - the code area + GAP is cleared after.
Layout = tuple[int, int, int, int, Callable, Callable]


def _ring(d, cx, cy, r, w, s):
    d.ellipse(((cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s), fill=255)
    d.ellipse(((cx - r + w) * s, (cy - r + w) * s, (cx + r - w) * s, (cy + r - w) * s), fill=0)


def lay_camera(n: int) -> Layout:
    B, S = 3, 7                                                    # landscape body: S extra modules each side
    W, H = n + 2 * (GAP + B + S), n + 2 * (GAP + B) + 4
    qx, qy = GAP + B + S, GAP + B + 4

    def sil(d, s):
        d.rounded_rectangle((0, 4 * s, W * s, H * s), radius=3 * s, fill=255)                          # body
        d.rounded_rectangle((W * 0.12 * s, 0, W * 0.42 * s, 5.5 * s), radius=1.2 * s, fill=255)          # viewfinder
        d.rounded_rectangle((W * 0.74 * s, 1.5 * s, W * 0.88 * s, 5 * s), radius=0.8 * s, fill=255)      # shutter

    def feat(d, s, qx, qy):
        _ring(d, qx + n / 2, qy + n / 2, n * 0.36, 2.2, s)                                              # lens ring
        _ring(d, qx + n / 2, qy + n / 2, n * 0.16, 1.4, s)
    return W, H, qx, qy, sil, feat


def lay_door(n: int) -> Layout:
    B = 3
    W, H = n + 2 * (GAP + B), n + 2 * (GAP + B) + int(n * 0.55)
    qx, qy = GAP + B, GAP + B

    def sil(d, s):
        d.rectangle((0, 0, W * s, H * s), fill=255)                                                     # frame
        d.rectangle((B * 0.5 * s, B * 0.5 * s, (W - B * 0.5) * s, H * s), fill=0)
        d.polygon([(B * s, B * s), ((W - B * 2.2) * s, (B + 1.5) * s), ((W - B * 2.2) * s, (H - 0.5) * s),
                   (B * s, H * s)], fill=255)                                                           # door leaf
        hx, hy = (W - B * 2.2 - 3.2), qy + n + GAP + (H - qy - n - GAP) * 0.45                         # handle (gap)
        d.rounded_rectangle(((hx - 1.2) * s, (hy - 2.2) * s, (hx + 1.2) * s, (hy + 2.2) * s), radius=0.8 * s, fill=0)

    def feat(d, s, qx, qy):
        d.rectangle(((qx + n * 0.9) * s, qy * s, (qx + n * 0.97) * s, (qy + n) * s), fill=255)           # leaf edge
    return W, H, qx, qy, sil, feat


def lay_robot(n: int) -> Layout:
    W, H = int(n * 1.95) + 2 * GAP, int(n * 1.7) + 2 * GAP
    qx, qy = GAP + 2, H - n - GAP - 6                                                                   # code = body

    def sil(d, s):
        bx0, bx1 = qx - GAP - 2, qx + n + GAP + 2
        d.rounded_rectangle((bx0 * s, (qy - GAP - 2) * s, bx1 * s, (H - 3) * s), radius=2.5 * s, fill=255)  # body
        d.rectangle(((bx0 - 2) * s, (H - 4) * s, (bx1 + 2) * s, H * s), fill=255)                       # base plate
        sh = (qx + n * 0.75, qy - GAP - 3)                                                               # shoulder
        el = (qx + n * 1.05, 4.5)                                                                        # elbow
        wr = (W - 5.0, qy * 0.55 + 4)                                                                    # wrist
        w = 3.6
        for a, b in ((sh, el), (el, wr)):
            d.line((a[0] * s, a[1] * s, b[0] * s, b[1] * s), fill=255, width=int(w * s))
        for (x, y), r in ((sh, 3.4), (el, 3.2), (wr, 2.8)):
            d.ellipse(((x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s), fill=255)
            d.ellipse(((x - r * 0.42) * s, (y - r * 0.42) * s, (x + r * 0.42) * s, (y + r * 0.42) * s), fill=0)
        gx, gy = wr[0], wr[1] + 2.5                                                                       # gripper
        d.line((gx * s, gy * s, gx * s, (gy + 3) * s), fill=255, width=int(2.4 * s))
        d.line(((gx - 2.2) * s, (gy + 3) * s, (gx + 2.2) * s, (gy + 3) * s), fill=255, width=int(1.8 * s))
        for dx in (-2.2, 2.2):
            d.line(((gx + dx) * s, (gy + 3) * s, (gx + dx) * s, (gy + 6) * s), fill=255, width=int(1.6 * s))

    def feat(d, s, qx, qy):
        _ring(d, qx + n * 0.5, qy + n * 0.5, n * 0.2, 1.8, s)                                           # base joint
    return W, H, qx, qy, sil, feat


def lay_pc(n: int) -> Layout:
    B = 2
    sw = n + 2 * (GAP + B)
    kb = max(6, int(n * 0.3))
    W, H = sw + 8, sw + kb + 1
    qx, qy = 4 + GAP + B, GAP + B

    def sil(d, s):
        d.rounded_rectangle((4 * s, 0, (4 + sw) * s, sw * s), radius=1.8 * s, fill=255)                  # screen + bezel
        d.polygon([(4 * s, (sw + 1) * s), ((4 + sw) * s, (sw + 1) * s), (W * s, H * s), (0, H * s)], fill=255)  # keyboard
        tp = (W / 2)
        d.rectangle(((tp - 5) * s, (H - 2.6) * s, (tp + 5) * s, (H - 1.0) * s), fill=0)                # touchpad gap

    def feat(d, s, qx, qy):
        pass
    return W, H, qx, qy, sil, feat


def lay_consumables(n: int) -> Layout:
    B = 4
    W, H = n + 2 * (GAP + B) + 2, n + 2 * (GAP + B) + 5
    qx, qy = GAP + B + 1, GAP + B + 5

    def sil(d, s):
        d.polygon([(0, 7 * s), (W * s, 7 * s), ((W - 2.5) * s, H * s), (2.5 * s, H * s)], fill=255)     # tub
        d.rectangle((0, 4.5 * s, W * s, 7.5 * s), fill=255)                                               # lid band
        d.arc(((W * 0.3) * s, 0, (W * 0.7) * s, 9 * s), 180, 360, fill=255, width=int(1.6 * s))           # handle

    def feat(d, s, qx, qy):
        pass
    return W, H, qx, qy, sil, feat


def lay_security(n: int) -> Layout:
    B = 4
    W = n + 2 * (GAP + B)
    H = int(W * 1.22)
    qx, qy = GAP + B, GAP + B

    def sil(d, s):
        d.polygon([(0, 1.5 * s), (W * 0.5 * s, 0), (W * s, 1.5 * s), (W * s, (qy + n + GAP + 1) * s),
                   (W * 0.5 * s, H * s), (0, (qy + n + GAP + 1) * s)], fill=255)                         # shield

    def feat(d, s, qx, qy):
        cx, cy = qx + n / 2, qy + n * 0.55                                                               # keyhole
        d.ellipse(((cx - 2.6) * s, (cy - 4.5) * s, (cx + 2.6) * s, (cy + 0.6) * s), fill=255)
        d.polygon([((cx - 1.5) * s, cy * s), ((cx + 1.5) * s, cy * s), ((cx + 2.4) * s, (cy + 5.5) * s),
                   ((cx - 2.4) * s, (cy + 5.5) * s)], fill=255)
    return W, H, qx, qy, sil, feat


def lay_server(n: int) -> Layout:
    B = 3
    W = n + 2 * (GAP + B)
    H = n + 2 * (GAP + B) + 12
    qx, qy = GAP + B, GAP + B + 6

    def sil(d, s):
        for y0, y1 in ((0, 5), (6.5, H - 6.5), (H - 5, H)):
            d.rounded_rectangle((0, y0 * s, W * s, y1 * s), radius=1.2 * s, fill=255)
        for y in (2.5, H - 2.5):                                                                          # drive LEDs
            for x in (W - 4, W - 7):
                d.ellipse(((x - 0.9) * s, (y - 0.9) * s, (x + 0.9) * s, (y + 0.9) * s), fill=0)

    def feat(d, s, qx, qy):
        pass
    return W, H, qx, qy, sil, feat


def lay_environment(n: int) -> Layout:
    B = 3
    W = n + 2 * (GAP + B) + 9
    H = n + 2 * (GAP + B)
    qx, qy = GAP + B, GAP + B

    def sil(d, s):
        d.rounded_rectangle((0, 0, (n + 2 * (GAP + B)) * s, H * s), radius=3 * s, fill=255)              # node
        tx = W - 4.2                                                                                      # thermometer
        d.rounded_rectangle(((tx - 1.8) * s, 1 * s, (tx + 1.8) * s, (H - 6) * s), radius=1.8 * s, fill=255)
        d.ellipse(((tx - 3.6) * s, (H - 8.5) * s, (tx + 3.6) * s, (H - 0.5) * s), fill=255)
        d.rounded_rectangle(((tx - 0.6) * s, 3 * s, (tx + 0.6) * s, (H - 8) * s), radius=0.6 * s, fill=0)

    def feat(d, s, qx, qy):
        pass
    return W, H, qx, qy, sil, feat


def lay_reusable(n: int) -> Layout:
    B = 4
    W = n + 2 * (GAP + B)
    H = n + 2 * (GAP + B) + 9
    qx, qy = GAP + B, GAP + B + 9

    def sil(d, s):
        d.rounded_rectangle((0, 9 * s, W * s, H * s), radius=1.5 * s, fill=255)                          # crate
        d.rectangle((0, 9 * s, W * s, 11 * s), fill=255)
        for r in (3, 5.5, 8):                                                                             # NFC waves
            d.arc(((W / 2 - r) * s, (9 - r) * s, (W / 2 + r) * s, (9 + r) * s), 215, 325, fill=255, width=int(1.4 * s))

    def feat(d, s, qx, qy):
        pass
    return W, H, qx, qy, sil, feat


def lay_frame(n: int) -> Layout:
    B = 3
    W = H = n + 2 * (GAP + B)
    qx = qy = GAP + B

    def sil(d, s):
        d.rounded_rectangle((0, 0, W * s, H * s), radius=4 * s, fill=255)

    def feat(d, s, qx, qy):
        pass
    return W, H, qx, qy, sil, feat


LAYOUTS = {"camera": lay_camera, "door": lay_door, "robot": lay_robot, "pc": lay_pc, "consumables": lay_consumables,
           "security": lay_security, "server": lay_server, "environment": lay_environment, "reusable": lay_reusable,
           "equipment": lay_frame, "device": lay_frame}


def _cells(draw_fn, W: int, H: int, *args) -> list[list[bool]]:
    img = Image.new("L", (W * SS, H * SS), 0)
    draw_fn(ImageDraw.Draw(img), SS, *args)
    small = img.resize((W, H), Image.BOX)
    px = small.load()
    return [[px[x, y] >= 128 for x in range(W)] for y in range(H)]


def _hash(x: int, y: int, seed: int) -> float:
    h = (x * 73856093) ^ (y * 19349663) ^ seed
    h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
    return (h & 0xFFFF) / 0xFFFF


# ---------------------------------------------------------------------------------------------- render ---
def shape_qr(code: str, cat: str, box: int = 16, tint: float = TINT, mod_shade: float = MOD_SHADE) -> Image.Image:
    """The object-shaped QR (RGB, white background). `tint`: how light the silhouette texture is (towards white)."""
    acc = ImageColor.getrgb(CATS[cat][0])
    m = matrix(code)
    n = len(m)
    W, H, qx, qy, sil, feat = LAYOUTS[cat](n)
    shape = _cells(sil, W, H)
    inner = _cells(lambda d, s: feat(d, s, qx, qy), W, H)
    # keep the code area + GAP white in the silhouette
    for y in range(max(0, qy - GAP), min(H, qy + n + GAP)):
        for x in range(max(0, qx - GAP), min(W, qx + n + GAP)):
            shape[y][x] = False
    edge = [[shape[y][x] and any(not (0 <= y + dy < H and 0 <= x + dx < W and shape[y + dy][x + dx])
                                 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))) for x in range(W)] for y in range(H)]
    pad = 4                                                               # outer white margin (modules)
    img = Image.new("RGB", ((W + 2 * pad) * box, (H + 2 * pad) * box), "white")
    d = ImageDraw.Draw(img)
    tex_dark, tex_light, edge_c = _mix(acc, (255, 255, 255), tint), _mix(acc, (255, 255, 255), 0.86), _mix(acc, NAVY, 0.1)
    feat_c = _mix(acc, NAVY, 0.28)
    mod_c = _mix(acc, NAVY, mod_shade)
    seed = sum(ord(ch) for ch in code) * 2654435761 & 0xFFFFFFFF
    r = box * 0.28
    for y in range(H):
        for x in range(W):
            if not shape[y][x]:
                continue
            X, Y = (x + pad) * box, (y + pad) * box
            if edge[y][x]:
                d.rounded_rectangle((X, Y, X + box - 1, Y + box - 1), radius=r * 0.5, fill=edge_c)
            else:
                d.rectangle((X, Y, X + box - 1, Y + box - 1), fill=tex_light)
                if _hash(x, y, seed) < 0.5:
                    d.rounded_rectangle((X + 1, Y + 1, X + box - 2, Y + box - 2), radius=r, fill=tex_dark)
    fx = ((0, 0), (n - 7, 0), (0, n - 7))
    for r_ in range(n):
        for c_ in range(n):
            if not m[r_][c_]:
                continue
            X, Y = (qx + c_ + pad) * box, (qy + r_ + pad) * box
            in_finder = any(fc <= c_ < fc + 7 and fr <= r_ < fr + 7 for fc, fr in fx)
            col = NAVY if in_finder else feat_c if inner[qy + r_][qx + c_] else mod_c
            d.rectangle((X, Y, X + box - 1, Y + box - 1), fill=col)
    for fc, fr in fx:                                                    # finder cores in the dark accent
        X, Y = (qx + fc + 2 + pad) * box, (qy + fr + 2 + pad) * box
        d.rectangle((X, Y, X + 3 * box - 1, Y + 3 * box - 1), fill=_mix(acc, NAVY, 0.5))
    return img


def plain_qr(code: str, cat: str, box: int = 16) -> Image.Image:
    """The reliable fallback: a standard QR (4-module quiet zone), dark modules in navy, finder cores in the accent."""
    acc = ImageColor.getrgb(CATS[cat][0])
    m = matrix(code)
    n = len(m)
    pad = 4
    img = Image.new("RGB", ((n + 2 * pad) * box, (n + 2 * pad) * box), "white")
    d = ImageDraw.Draw(img)
    for r_ in range(n):
        for c_ in range(n):
            if m[r_][c_]:
                X, Y = (c_ + pad) * box, (r_ + pad) * box
                d.rectangle((X, Y, X + box - 1, Y + box - 1), fill=NAVY)
    for fc, fr in ((0, 0), (n - 7, 0), (0, n - 7)):
        X, Y = (fc + 2 + pad) * box, (fr + 2 + pad) * box
        d.rectangle((X, Y, X + 3 * box - 1, Y + 3 * box - 1), fill=_mix(acc, NAVY, 0.5))
    return img


def decodes(img: Image.Image, code: str) -> bool:
    """OpenCV must read the code back at full size, half and a third (a phone across a desk)."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return True
    det = cv2.QRCodeDetector()
    hits = 0
    for scale in (1.0, 0.5, 0.33):
        a = img if scale == 1.0 else img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
        hits += det.detectAndDecode(np.array(a)[:, :, ::-1])[0] == code
    return hits >= 2


def _font(px: int, bold=True):
    for f in (("DejaVuSans-Bold.ttf", "arialbd.ttf") if bold else ("DejaVuSans.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(f, px)
        except OSError:
            continue
    return ImageFont.load_default(px)


def _fit(d, text, max_w, px, bold=True):
    while px > 12:
        f = _font(px, bold)
        if d.textlength(text, font=f) <= max_w:
            return f
        px -= 1
    return _font(12, bold)


def card(item: dict, box: int = 16, shaped: bool = True) -> tuple[Image.Image, str]:
    """A printable white marker card; returns (image, 'shape' | 'plain')."""
    cat = category(item)
    acc = ImageColor.getrgb(CATS[cat][0])
    art, kind = None, "plain"
    if shaped:
        art = shape_qr(item["code"], cat, box)
        if decodes(art, item["code"]):
            kind = "shape"
        else:
            art = None
    if art is None:
        art = plain_qr(item["code"], cat, box)
    side = box * 2
    foot = box * 9
    Wc = max(art.width, box * 46) + 2 * side
    Hc = art.height + foot + side
    c = Image.new("RGB", (Wc, Hc), "white")
    c.paste(art, ((Wc - art.width) // 2, side // 2))
    d = ImageDraw.Draw(c)
    y = side // 2 + art.height + box
    d.rectangle(((Wc - box * 14) // 2, y, (Wc + box * 14) // 2, y + max(3, box // 5)), fill=acc)      # thin accent
    name = (item.get("name") or "")[:42]
    d.text((Wc / 2, y + box * 1.2), name, fill=NAVY, font=_fit(d, name, Wc - 2 * side, int(box * 2.3)), anchor="mt")
    sub = item["code"] + (f"  ·  {item['lab_code']}" if item.get("lab_code") else "")
    d.text((Wc / 2, y + box * 4.4), sub, fill=(71, 85, 105), font=_fit(d, sub, Wc - 2 * side, int(box * 1.5), bold=False), anchor="mt")
    d.text((Wc / 2, y + box * 6.6), CATS[cat][1], fill=_mix(acc, NAVY, 0.2), font=_font(int(box * 1.15)), anchor="mt")
    return c, kind


@functools.lru_cache(maxsize=256)
def _png_cached(code: str, name: str, type_: str, lab: str, kind: str, box: int) -> bytes:
    img, _ = card({"code": code, "name": name, "type": type_, "lab_code": lab or None, "kind": kind}, box)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def png(item: dict, box: int = 16) -> bytes:
    return _png_cached(item["code"], item.get("name") or "", item.get("type") or "", item.get("lab_code") or "",
                       item.get("kind") or "", box)


def sheet_pdf(items: list[dict], cols: int = 3, rows: int = 3) -> bytes:
    """White A4 pages at 300 dpi; each card drawn with the largest whole module size that fits its cell (no
    rescaling - sharp modules), dashed cut lines."""
    PW, PH, m = 2480, 3508, 118                                   # A4 at 300 dpi, 1 cm margin
    cw, ch = (PW - 2 * m) // cols, (PH - 2 * m) // rows
    pages: list[Image.Image] = []
    for start in range(0, max(1, len(items)), cols * rows):
        page = Image.new("RGB", (PW, PH), "white")
        d = ImageDraw.Draw(page)
        for k, it in enumerate(items[start:start + cols * rows]):
            probe = Image.open(io.BytesIO(png(it, 8)))              # size at 8 px/module -> the box that fits
            box = max(6, min(int(8 * (cw - 40) / probe.width), int(8 * (ch - 40) / probe.height)))
            c = Image.open(io.BytesIO(png(it, box)))
            x0, y0 = m + (k % cols) * cw, m + (k // cols) * ch
            page.paste(c, (x0 + (cw - c.width) // 2, y0 + (ch - c.height) // 2))
            for x in range(x0, x0 + cw, 24):
                d.line((x, y0, x + 12, y0), fill="#cbd5e1", width=2); d.line((x, y0 + ch, x + 12, y0 + ch), fill="#cbd5e1", width=2)
            for y in range(y0, y0 + ch, 24):
                d.line((x0, y, x0, y + 12), fill="#cbd5e1", width=2); d.line((x0 + cw, y, x0 + cw, y + 12), fill="#cbd5e1", width=2)
        pages.append(page)
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", resolution=300, save_all=True, append_images=pages[1:])
    return buf.getvalue()
