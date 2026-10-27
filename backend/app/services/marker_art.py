"""
Themed asset markers (2026-10-27, owner: "make the QR codes more creative - a camera for the ESP32-CAM, security
for the security nodes, a robot for the robots, a door for the master").

Each marker is a normal QR code (error correction H: up to ~30 % of the modules may be covered and it still reads)
with a small badge in the middle showing what the asset is, a coloured frame and a header with the same icon.
The badge covers well under the H budget; every design is checked with OpenCV's decoder in the tests.
Icons are drawn with plain Pillow shapes - no image files, no fonts to download.
"""
from __future__ import annotations

import io
from typing import Callable

import qrcode
from PIL import Image, ImageColor, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_H

# theme per marker type: (accent colour, short header label, icon)
Icon = Callable[..., None]


def _camera(d, cx, cy, s, c, bg="white"):                    # ESP32-CAM / entry camera: compact camera body + lens
    d.rounded_rectangle((cx - s, cy - s * 0.6, cx + s, cy + s * 0.7), radius=s * 0.18, fill=c)
    d.rectangle((cx - s * 0.45, cy - s * 0.85, cx + s * 0.1, cy - s * 0.55), fill=c)
    d.ellipse((cx - s * 0.48, cy - s * 0.38, cx + s * 0.48, cy + s * 0.58), fill=bg)
    d.ellipse((cx - s * 0.28, cy - s * 0.18, cx + s * 0.28, cy + s * 0.38), fill=c)


def _security(d, cx, cy, s, c, bg="white"):                  # security camera: shield with a dome camera eye
    d.polygon([(cx - s * 0.85, cy - s * 0.8), (cx, cy - s), (cx + s * 0.85, cy - s * 0.8), (cx + s * 0.8, cy + s * 0.1),
               (cx, cy + s), (cx - s * 0.8, cy + s * 0.1)], fill=c)
    d.ellipse((cx - s * 0.45, cy - s * 0.4, cx + s * 0.45, cy + s * 0.4), fill=bg)
    d.ellipse((cx - s * 0.2, cy - s * 0.15, cx + s * 0.2, cy + s * 0.25), fill=c)


def _robot(d, cx, cy, s, c, bg="white"):     # industrial robot arm: pedestal, shoulder, two links, wrist, gripper
    w = max(3, int(s * 0.34))
    d.rounded_rectangle((cx - s * 0.85, cy + s * 0.68, cx + s * 0.15, cy + s), radius=s * 0.06, fill=c)       # base
    d.pieslice((cx - s * 0.62, cy + s * 0.38, cx - s * 0.08, cy + s * 0.98), 180, 360, fill=c)               # turret
    sh, el, wr = (cx - s * 0.35, cy + s * 0.5), (cx - s * 0.5, cy - s * 0.25), (cx + s * 0.4, cy - s * 0.6)
    d.line((*sh, *el), fill=c, width=w)
    d.line((*el, *wr), fill=c, width=int(w * 0.85))
    for (x, y), r in ((sh, 0.62), (el, 0.6), (wr, 0.5)):                                                   # joints
        d.ellipse((x - w * r, y - w * r, x + w * r, y + w * r), fill=c)
    for (x, y), r in ((sh, 0.25), (el, 0.25)):
        d.ellipse((x - w * r, y - w * r, x + w * r, y + w * r), fill=bg)
    g = max(2, int(w * 0.4))                                                                               # gripper
    d.line((*wr, cx + s * 0.78, cy - s * 0.42), fill=c, width=g)
    d.line((cx + s * 0.78, cy - s * 0.42, cx + s * 0.98, cy - s * 0.18), fill=c, width=g)
    d.line((*wr, cx + s * 0.62, cy - s * 0.92), fill=c, width=g)
    d.line((cx + s * 0.62, cy - s * 0.92, cx + s * 0.92, cy - s * 0.9), fill=c, width=g)


def _door(d, cx, cy, s, c, bg="white"):      # master door controller: frame + door swung open + handle
    w = max(2, int(s * 0.16))
    d.rectangle((cx - s * 0.75, cy - s, cx + s * 0.75, cy + s), outline=c, width=w)
    d.polygon([(cx - s * 0.75, cy - s), (cx + s * 0.35, cy - s * 0.75), (cx + s * 0.35, cy + s * 0.8),
               (cx - s * 0.75, cy + s)], fill=c)
    d.ellipse((cx + s * 0.05, cy - s * 0.02, cx + s * 0.23, cy + s * 0.16), fill=bg)


def _pc(d, cx, cy, s, c, bg="white"):                        # lab PC: monitor on a stand
    d.rounded_rectangle((cx - s, cy - s * 0.8, cx + s, cy + s * 0.45), radius=s * 0.12, fill=c)
    d.rectangle((cx - s * 0.8, cy - s * 0.6, cx + s * 0.8, cy + s * 0.25), fill=bg)
    d.rectangle((cx - s * 0.12, cy + s * 0.45, cx + s * 0.12, cy + s * 0.75), fill=c)
    d.rectangle((cx - s * 0.5, cy + s * 0.75, cx + s * 0.5, cy + s * 0.92), fill=c)


def _server(d, cx, cy, s, c, bg="white"):                    # face server: rack units with a face dot pair
    for i in range(3):
        y0 = cy - s + i * s * 0.7
        d.rounded_rectangle((cx - s * 0.8, y0, cx + s * 0.8, y0 + s * 0.55), radius=s * 0.1, fill=c)
        d.ellipse((cx + s * 0.4, y0 + s * 0.18, cx + s * 0.6, y0 + s * 0.38), fill=bg)


def _sensor(d, cx, cy, s, c, bg="white"):                    # sensor node: thermometer + signal waves
    d.rounded_rectangle((cx - s * 0.6, cy - s, cx - s * 0.2, cy + s * 0.4), radius=s * 0.2, fill=c)
    d.ellipse((cx - s * 0.75, cy + s * 0.2, cx - s * 0.05, cy + s * 0.9), fill=c)
    for r in (0.35, 0.65, 0.95):
        d.arc((cx - r * s + s * 0.2, cy - r * s - s * 0.2, cx + r * s + s * 0.2, cy + r * s - s * 0.2), 300, 60, fill=c,
              width=max(2, int(s * 0.14)))


def _bin(d, cx, cy, s, c, bg="white"):                       # consumables bin: box with lid and parts
    d.polygon([(cx - s * 0.85, cy - s * 0.3), (cx + s * 0.85, cy - s * 0.3), (cx + s * 0.65, cy + s), (cx - s * 0.65, cy + s)],
              fill=c)
    d.rectangle((cx - s, cy - s * 0.55, cx + s, cy - s * 0.32), fill=c)
    for x in (-0.4, 0.0, 0.4):
        d.ellipse((cx + (x - 0.12) * s, cy - s * 0.95, cx + (x + 0.12) * s, cy - s * 0.65), fill=c)


def _tool(d, cx, cy, s, c, bg="white"):                      # equipment / reusable item: wrench
    w = max(3, int(s * 0.3))
    d.line((cx - s * 0.7, cy + s * 0.7, cx + s * 0.35, cy - s * 0.35), fill=c, width=w)
    d.ellipse((cx + s * 0.05, cy - s, cx + s, cy - s * 0.05), fill=c)
    d.polygon([(cx + s * 0.55, cy - s * 1.0), (cx + s * 1.0, cy - s * 0.55), (cx + s * 0.6, cy - s * 0.45),
               (cx + s * 0.45, cy - s * 0.6)], fill=bg)


def _chip(d, cx, cy, s, c, bg="white"):                      # any other device: a chip with pins
    d.rounded_rectangle((cx - s * 0.6, cy - s * 0.6, cx + s * 0.6, cy + s * 0.6), radius=s * 0.1, fill=c)
    for k in (-0.35, 0.0, 0.35):
        for a, b in (((-0.95, k), (-0.6, k)), ((0.6, k), (0.95, k)), ((k, -0.95), (k, -0.6)), ((k, 0.6), (k, 0.95))):
            d.line((cx + a[0] * s, cy + a[1] * s, cx + b[0] * s, cy + b[1] * s), fill=c, width=max(2, int(s * 0.12)))
    d.ellipse((cx - s * 0.2, cy - s * 0.2, cx + s * 0.2, cy + s * 0.2), fill=bg)


THEMES: dict[str, tuple[str, str, Icon]] = {
    "Entry camera": ("#7c3aed", "ENTRY CAMERA", _camera),
    "Security camera": ("#dc2626", "SECURITY", _security),
    "Robot": ("#ea580c", "ROBOT", _robot),
    "Door controller (master ESP32)": ("#0f766e", "DOOR MASTER", _door),
    "Lab PC": ("#2563eb", "LAB PC", _pc),
    "Face server": ("#9333ea", "FACE SERVER", _server),
    "Sensor node": ("#16a34a", "SENSOR NODE", _sensor),
    "Consumables bin": ("#ca8a04", "CONSUMABLES", _bin),
}
DEFAULT_DEVICE = ("#475569", "DEVICE", _chip)
DEFAULT_ASSET = ("#0369a1", "EQUIPMENT", _tool)


def theme(item: dict) -> tuple[str, str, Icon]:
    t = THEMES.get(item.get("type", ""))
    if t:
        return t
    name = (item.get("name") or "").lower()
    if "cam" in name:
        return THEMES["Entry camera"]
    if "robot" in name or "ur5" in name or "fanuc" in name:
        return THEMES["Robot"]
    return DEFAULT_DEVICE if item.get("kind") == "device" else DEFAULT_ASSET


def _font(px: int):
    for f in ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(f, px)
        except OSError:
            continue
    return ImageFont.load_default(px)


def _fit(d: ImageDraw.ImageDraw, text: str, max_w: int, px: int):
    while px > 10:
        f = _font(px)
        if d.textlength(text, font=f) <= max_w:
            return f
        px -= 1
    return _font(10)


NAVY = (11, 18, 32)
DOT = 0.44                 # the true-colour centre of every module (fraction of its width): what the scanner reads
SHADE = 0.25               # inside the picture, dark modules are this much darker and light ones this much lighter


def _mix(c, d, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(c, d))


def art_qr(code: str, accent: str, icon: Icon, box: int = 12, border: int = 4) -> Image.Image:
    """The QR code IS the picture (halftone QR): the asset's icon is painted across the whole code in its colour, and
    every module keeps a true-colour dot in its centre - which is where a scanner samples. Inside the picture each
    module is also shaded a little towards its true colour, so it binarises correctly even when the dot blurs.
    The three finder squares stay plain navy/white (they are what a scanner locks onto first)."""
    qr = qrcode.QRCode(version=6, error_correction=ERROR_CORRECT_H, box_size=box, border=0)
    qr.add_data(code)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    size = (n + 2 * border) * box
    acc = ImageColor.getrgb(accent)
    dark_in, light_in = _mix(acc, NAVY, SHADE), _mix(acc, (255, 255, 255), SHADE)
    # the picture: a big icon over the code area, as a mask (finder squares kept clear)
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    c0 = size / 2
    icon(md, c0, c0, n * box * 0.47, 255, 0)
    o = border * box
    for fx, fy in ((0, 0), (n - 8, 0), (0, n - 8)):
        md.rectangle((o + fx * box, o + fy * box, o + (fx + 8) * box - 1, o + (fy + 8) * box - 1), fill=0)
    plain = Image.new("RGB", (size, size), "white")
    pic = Image.new("RGB", (size, size), "white")
    pd, cd = ImageDraw.Draw(plain), ImageDraw.Draw(pic)
    k = (1 - DOT) / 2 * box
    for r in range(n):
        for c in range(n):
            x, y = o + c * box, o + r * box
            dark = m[r][c]
            pd.rectangle((x, y, x + box - 1, y + box - 1), fill=NAVY if dark else "white")
            cd.rectangle((x, y, x + box - 1, y + box - 1), fill=dark_in if dark else light_in)
            cd.rectangle((x + k, y + k, x + box - k - 1, y + box - k - 1), fill=NAVY if dark else "white")
    plain.paste(pic, (0, 0), mask)
    return plain


def render(item: dict, box: int = 12) -> Image.Image:
    """One printable marker card (RGB): header band + the picture-QR + name and code."""
    accent, label, icon = theme(item)
    q = art_qr(item["code"], accent, icon, box)

    pad, head, foot = box * 2, box * 6, box * 9
    W = q.width + 2 * pad
    card = Image.new("RGB", (W, q.height + head + foot + pad), "white")
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, W - 1, card.height - 1), radius=box * 2, outline=accent, width=max(4, box // 2))
    d.rounded_rectangle((0, 0, W - 1, head), radius=box * 2, fill=accent)
    d.rectangle((0, head - box * 2, W - 1, head), fill=accent)
    ic = head * 0.32
    icon(d, pad + ic, head / 2, ic, "white", accent)
    hf = _fit(d, label, W - 3 * pad - 2 * ic, int(head * 0.42))
    d.text((pad + 2 * ic + pad * 0.6, head / 2), label, fill="white", font=hf, anchor="lm")
    card.paste(q, (pad, head + pad // 2))
    y = head + pad // 2 + q.height + box
    d.text((W / 2, y), item.get("name", "")[:44], fill="#0b1220", font=_fit(d, item.get("name", "")[:44], W - 2 * pad, int(box * 2.6)),
           anchor="mt")
    sub = item["code"] + (f"  ·  {item['lab_code']}" if item.get("lab_code") else "")
    d.text((W / 2, y + box * 3.6), sub, fill="#475569", font=_fit(d, sub, W - 2 * pad, int(box * 1.8)), anchor="mt")
    return card


def png(item: dict) -> bytes:
    buf = io.BytesIO()
    render(item).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def sheet_pdf(items: list[dict], cols: int = 3, rows: int = 4) -> bytes:
    """A4 pages (150 dpi) of marker cards, cut lines between them. The phone opens it and prints/shares it - the
    reliable way to print from iOS/Android (window.print() of the live page is unreliable there)."""
    PW, PH, m = 1240, 1754, 60                                   # A4 at 150 dpi, 1 cm margin
    cw, ch = (PW - 2 * m) // cols, (PH - 2 * m) // rows
    pages: list[Image.Image] = []
    for start in range(0, max(1, len(items)), cols * rows):
        page = Image.new("RGB", (PW, PH), "white")
        d = ImageDraw.Draw(page)
        for k, it in enumerate(items[start:start + cols * rows]):
            c = render(it)
            s = min((cw - 24) / c.width, (ch - 24) / c.height)
            c = c.resize((int(c.width * s), int(c.height * s)), Image.LANCZOS)
            x0, y0 = m + (k % cols) * cw, m + (k // cols) * ch
            page.paste(c, (x0 + (cw - c.width) // 2, y0 + (ch - c.height) // 2))
            d.rectangle((x0, y0, x0 + cw, y0 + ch), outline="#cbd5e1", width=1)
        pages.append(page)
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", resolution=150, save_all=True, append_images=pages[1:])
    return buf.getvalue()
