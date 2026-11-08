---
type: "source-mirror"
source_kind: "source-code"
source_path: "backend/app/services/marker_art.py"
source_hash: "f306aeb9fd65411cc9d2bc3d5ccdf05388506672e0f6046902b9b1c534965001"
generated: true
updated: "2026-11-04T00:02:39+02:00"
---
> Read-only mirror of `backend/app/services/marker_art.py` - edit the original in the repository, not this note.

Systems: none

```py
"""
Themed asset markers (2026-10-27, owner: "make the QR codes more creative - a camera for the ESP32-CAM, security
for the security nodes, a robot for the robots, a door for the master").

Each marker is a normal QR code (error correction H: up to ~30 % of the modules may be covered and it still reads)
with a small badge in the middle showing what the asset is, a coloured frame and a header with the same icon.
The badge covers well under the H budget; every design is checked with OpenCV's decoder in the tests.
Icons are drawn with plain Pillow shapes - no image files, no fonts to download.
"""
from __future__ import annotations

import functools
import io
from typing import Callable, Optional

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


def _reusable(d, cx, cy, s, c, bg="white"):                  # reusable-items node: crate + a dev board + NFC waves
    d.rounded_rectangle((cx - s * 0.95, cy - s * 0.15, cx + s * 0.95, cy + s), radius=s * 0.1, fill=c)
    d.rectangle((cx - s * 0.95, cy - s * 0.32, cx + s * 0.95, cy - s * 0.18), fill=c)
    d.rounded_rectangle((cx - s * 0.6, cy + s * 0.1, cx + s * 0.35, cy + s * 0.75), radius=s * 0.06, fill=bg)
    for k in range(5):                                                                # header pins of the board
        x = cx - s * 0.5 + k * s * 0.18
        d.rectangle((x, cy + s * 0.16, x + s * 0.08, cy + s * 0.26), fill=c)
    d.rectangle((cx - s * 0.25, cy + s * 0.35, cx + s * 0.05, cy + s * 0.6), fill=c)                     # MCU
    for r in (0.3, 0.55, 0.8):                                                         # NFC waves above the crate
        d.arc((cx + s * 0.1 - r * s, cy - s * 0.45 - r * s, cx + s * 0.1 + r * s, cy - s * 0.45 + r * s), 200, 340,
              fill=c, width=max(2, int(s * 0.12)))


def _consumables(d, cx, cy, s, c, bg="white"):               # consumables node: bin on a scale + a resistor
    d.polygon([(cx - s * 0.85, cy - s * 0.55), (cx + s * 0.85, cy - s * 0.55), (cx + s * 0.65, cy + s * 0.6),
               (cx - s * 0.65, cy + s * 0.6)], fill=c)
    d.rectangle((cx - s, cy + s * 0.72, cx + s, cy + s * 0.95), fill=c)                                  # load cell
    w = max(2, int(s * 0.11))                                                                              # resistor
    pts = [(cx - s * 0.6, cy), (cx - s * 0.3, cy)]
    for k in range(5):
        pts.append((cx - s * 0.25 + k * s * 0.11, cy + (-1 if k % 2 == 0 else 1) * s * 0.2))
    pts += [(cx + s * 0.3, cy), (cx + s * 0.6, cy)]
    d.line(pts, fill=bg, width=w, joint="curve")
    for x in (-0.55, 0.0, 0.55):                                                        # parts heaped on top
        d.ellipse((cx + (x - 0.13) * s, cy - s * 0.98, cx + (x + 0.13) * s, cy - s * 0.72), fill=c)


THEMES: dict[str, tuple[str, str, Icon]] = {
    "Entry camera": ("#7c3aed", "ENTRY CAMERA", _camera),
    "Security camera": ("#dc2626", "SECURITY NODE", _security),
    "Robot": ("#ea580c", "ROBOT", _robot),
    "Door controller (master ESP32)": ("#0f766e", "DOOR MASTER", _door),
    "Lab PC": ("#2563eb", "LAB PC", _pc),
    "Face server": ("#9333ea", "FACE SERVER", _server),
    "Environment node": ("#16a34a", "ENVIRONMENT NODE", _sensor),
    "Sensor node": ("#16a34a", "SENSOR NODE", _sensor),
    "Consumables bin node": ("#ca8a04", "CONSUMABLES NODE", _consumables),
    "Consumables bin": ("#ca8a04", "CONSUMABLES BIN", _bin),
    "Reusable-items bin node": ("#0891b2", "REUSABLE ITEMS", _reusable),
}
DEFAULT_DEVICE = ("#64748b", "DEVICE", _chip)
DEFAULT_ASSET = ("#0284c7", "EQUIPMENT", _tool)


def theme(item: dict) -> tuple[str, str, Icon]:
    t = THEMES.get(item.get("type", ""))
    if t:
        return t
    name = (item.get("name") or "").lower()
    if "cam" in name:
        return THEMES["Entry camera"]
    if "robot" in name or "ur5" in name or "fanuc" in name:
        return THEMES["Robot"]
    if item.get("type") == "Reusable-bin item":
        return ("#0891b2", "REUSABLE ITEM", _tool)
    return DEFAULT_DEVICE if item.get("kind") == "device" else DEFAULT_ASSET


def _font(px: int, bold: bool = True):
    names = ("DejaVuSans-Bold.ttf", "arialbd.ttf") if bold else ("DejaVuSans.ttf", "arial.ttf")
    for f in names:
        try:
            return ImageFont.truetype(f, px)
        except OSError:
            continue
    return ImageFont.load_default(px)


def _fit(d: ImageDraw.ImageDraw, text: str, max_w: float, px: int, bold: bool = True):
    while px > 10:
        f = _font(px, bold)
        if d.textlength(text, font=f) <= max_w:
            return f
        px -= 1
    return _font(10, bold)


NAVY = (11, 18, 32)
CARD = (8, 14, 28)          # card background (dark navy)
DOT = 0.44                  # the true-colour centre of every module (fraction of its width): what the scanner reads
SHADE = 0.25                # inside the picture, dark modules are this much darker and light ones this much lighter
QUIET = 4                   # quiet zone in modules (the QR standard's minimum)
MOD_ROUND = 0.0             # module corner rounding (fraction of a module); measured: rounding hurts decoding
FINDER_ROUND = 0.0          # finder-ring corner rounding (fraction of a module)


def _mix(c, d, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(c, d))


def _finders(n: int):
    return ((0, 0), (n - 7, 0), (0, n - 7))


def _in_finder(r: int, c: int, n: int) -> bool:
    return any(fr <= r < fr + 7 and fc <= c < fc + 7 for fc, fr in _finders(n))


def art_qr(code: str, accent: str, icon: Optional[Icon], box: int = 16, art: bool = True) -> Image.Image:
    """The QR code IS the picture (halftone QR). Real QR data (error correction H); every module keeps a true-colour
    centre where a scanner samples it, and the asset's motif is painted across the code around those centres.
    Modules are rounded squares; the three finder patterns are drawn as rounded navy rings with an accent-dark
    core (still dark-on-light, at their exact module positions). art=False = the plain fallback (no motif)."""
    qr = qrcode.QRCode(version=6, error_correction=ERROR_CORRECT_H, box_size=box, border=0)
    qr.add_data(code)
    qr.make(fit=True)
    m = qr.get_matrix()
    n = len(m)
    size = (n + 2 * QUIET) * box
    acc = ImageColor.getrgb(accent)
    core = _mix(acc, NAVY, 0.55)
    dark_in, light_in = _mix(acc, NAVY, SHADE), _mix(acc, (255, 255, 255), SHADE)
    o = QUIET * box
    mask = Image.new("L", (size, size), 0)
    if art and icon is not None:
        md = ImageDraw.Draw(mask)
        icon(md, size / 2, size / 2, n * box * 0.47, 255, 0)
        for fc, fr in _finders(n):                    # finder squares + their separators stay clear of the picture
            x0, y0 = o + (fc - (1 if fc else 0)) * box, o + (fr - (1 if fr else 0)) * box
            md.rectangle((x0, y0, x0 + 8 * box - 1, y0 + 8 * box - 1), fill=0)
    plain = Image.new("RGB", (size, size), "white")
    pic = Image.new("RGB", (size, size), "white")
    pd, cd = ImageDraw.Draw(plain), ImageDraw.Draw(pic)
    k = (1 - DOT) / 2 * box
    rad = box * MOD_ROUND
    for r in range(n):
        for c in range(n):
            if _in_finder(r, c, n):
                continue
            x, y = o + c * box, o + r * box
            dark = m[r][c]
            if dark:
                pd.rounded_rectangle((x, y, x + box - 1, y + box - 1), radius=rad, fill=NAVY)
            cd.rectangle((x, y, x + box - 1, y + box - 1), fill=dark_in if dark else light_in)
            cd.rounded_rectangle((x + k, y + k, x + box - k - 1, y + box - k - 1), radius=box * 0.12,
                                 fill=NAVY if dark else "white")
    plain.paste(pic, (0, 0), mask)
    for fc, fr in _finders(n):
        x, y = o + fc * box, o + fr * box
        f = box * FINDER_ROUND
        pd.rounded_rectangle((x, y, x + 7 * box - 1, y + 7 * box - 1), radius=f * 1.6, fill=NAVY)
        pd.rounded_rectangle((x + box, y + box, x + 6 * box - 1, y + 6 * box - 1), radius=f * 1.1, fill="white")
        pd.rounded_rectangle((x + 2 * box, y + 2 * box, x + 5 * box - 1, y + 5 * box - 1), radius=f * 0.8, fill=core)
    return plain


def decodes(img: Image.Image, code: str) -> bool:
    """Self-check behind the automatic fallback: OpenCV's decoder (the one the door's face server uses) must read
    the code back at half and a third of its size (how small it looks to a phone across a desk) and at 3 of 4
    sizes overall. (Very large images sometimes miss in OpenCV alone - a phone never sees the code that big.)"""
    try:
        import cv2
        import numpy as np
    except ImportError:                                # no decoder here: trust the design (the tests check it)
        return True
    det = cv2.QRCodeDetector()
    ok = {}
    for scale in (1.0, 0.75, 0.5, 0.33):
        a = img if scale == 1.0 else img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
        ok[scale] = det.detectAndDecode(np.array(a.convert("RGB"))[:, :, ::-1])[0] == code
    return ok[0.5] and ok[0.33] and sum(ok.values()) >= 3


def _traces(d: ImageDraw.ImageDraw, W: int, H: int, accent, seed: str, unit: int):
    """Subtle circuit traces (deterministic per marker): 90/45 degree runs ending in vias."""
    import random
    rnd = random.Random(seed)
    col = _mix(accent, CARD, 0.78)
    w = max(1, unit // 6)
    for _ in range(16):
        x, y = rnd.choice([(rnd.randrange(W), rnd.choice((0, H))), (rnd.choice((0, W)), rnd.randrange(H))])
        pts = [(x, y)]
        for _ in range(rnd.randint(2, 4)):
            dx, dy = rnd.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)])
            L = rnd.randint(2, 7) * unit
            x, y = max(0, min(W, x + dx * L)), max(0, min(H, y + dy * L))
            pts.append((x, y))
        d.line(pts, fill=col, width=w)
        d.ellipse((x - unit * 0.35, y - unit * 0.35, x + unit * 0.35, y + unit * 0.35), outline=col, width=w)


def render(item: dict, box: int = 16) -> Image.Image:
    """One marker card: dark navy with circuit traces, a restrained glow in the category colour, a light QR panel
    whose modules carry the asset's motif, and the name / record key / location. If the artistic code does not
    read back, the same card is drawn with a plain QR (never a broken one)."""
    from PIL import ImageFilter
    accent, label, icon = theme(item)
    acc = ImageColor.getrgb(accent)
    q = art_qr(item["code"], accent, icon, box)
    if not decodes(q, item["code"]):
        q = art_qr(item["code"], accent, icon, box, art=False)
    pad, head = box * 3, box * 7
    foot = box * 9
    W = q.width + 2 * pad
    H = head + q.height + foot + pad
    card = Image.new("RGB", (W, H), CARD)
    d = ImageDraw.Draw(card)
    _traces(d, W, H, acc, item["code"], box)
    # glow behind the QR panel
    glow = Image.new("RGB", (W, H), CARD)
    gd = ImageDraw.Draw(glow)
    qx, qy = pad, head
    gd.rounded_rectangle((qx - box, qy - box, qx + q.width + box, qy + q.height + box), radius=box * 2.2, fill=_mix(acc, CARD, 0.35))
    glow = glow.filter(ImageFilter.GaussianBlur(box * 1.4))
    card = Image.blend(card, glow, 0.45)
    d = ImageDraw.Draw(card)
    _traces(d, W, H, acc, item["code"] + "#2", box)
    d.rounded_rectangle((qx - box * 0.4, qy - box * 0.4, qx + q.width + box * 0.4, qy + q.height + box * 0.4),
                        radius=box * 1.6, fill="white", outline=accent, width=max(2, box // 5))
    card.paste(q, (qx, qy))
    # header: icon chip + category
    ic = box * 2.1
    d.rounded_rectangle((pad, box * 1.6, pad + ic * 2, box * 1.6 + ic * 2), radius=box * 0.8, fill=accent)
    icon(d, pad + ic, box * 1.6 + ic, ic * 0.62, "white", accent)
    d.text((pad + ic * 2 + box, box * 1.6 + ic), label, fill=_mix(acc, (255, 255, 255), 0.45),
           font=_fit(d, label, W - 2 * pad - ic * 2 - box, int(box * 2.1)), anchor="lm")
    d.line((pad, head - box * 1.6, W - pad, head - box * 1.6), fill=_mix(acc, CARD, 0.55), width=max(1, box // 8))
    # footer: name, record key, location
    y = qy + q.height + box * 1.4
    name = (item.get("name") or "")[:44]
    d.text((W / 2, y), name, fill="white", font=_fit(d, name, W - 2 * pad, int(box * 2.4)), anchor="mt")
    sub = item["code"]
    d.text((W / 2, y + box * 3.3), sub, fill=_mix(acc, (255, 255, 255), 0.55),
           font=_fit(d, sub, W - 2 * pad, int(box * 1.6), bold=False), anchor="mt")
    loc = " · ".join(x for x in (item.get("type"), item.get("lab_code")) if x)
    if loc:
        d.text((W / 2, y + box * 5.6), loc, fill=(148, 163, 184),
               font=_fit(d, loc, W - 2 * pad, int(box * 1.4), bold=False), anchor="mt")
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=box * 2, outline=_mix(acc, CARD, 0.3), width=max(2, box // 6))
    return card


@functools.lru_cache(maxsize=256)
def _png_cached(code: str, name: str, type_: str, lab: str, kind: str, box: int) -> bytes:
    buf = io.BytesIO()
    render({"code": code, "name": name, "type": type_, "lab_code": lab or None, "kind": kind}, box).save(
        buf, "PNG", optimize=True)
    return buf.getvalue()


def png(item: dict, box: int = 16) -> bytes:
    return _png_cached(item["code"], item.get("name") or "", item.get("type") or "", item.get("lab_code") or "",
                       item.get("kind") or "", box)


def sheet_pdf(items: list[dict], cols: int = 3, rows: int = 3) -> bytes:
    """A4 pages at 300 dpi, cards drawn at the size they print (no rescaling = sharp modules), cut lines between
    them. 3 x 3 per page: each card ~6.5 cm wide, the code itself ~5.5 cm."""
    PW, PH, m = 2480, 3508, 118                                  # A4 at 300 dpi, 1 cm margin
    cw, ch = (PW - 2 * m) // cols, (PH - 2 * m) // rows
    # the module size that fits a card in its cell: card width = (n + 2*QUIET + 6) * box, height ~ (n+8+19) * box
    n = 41 + 2 * QUIET
    box = max(8, min((cw - 30) // (n + 6), (ch - 30) // (n + 19)))
    pages: list[Image.Image] = []
    for start in range(0, max(1, len(items)), cols * rows):
        page = Image.new("RGB", (PW, PH), "white")
        d = ImageDraw.Draw(page)
        for k, it in enumerate(items[start:start + cols * rows]):
            c = Image.open(io.BytesIO(png(it, box)))
            x0, y0 = m + (k % cols) * cw, m + (k // cols) * ch
            page.paste(c, (x0 + (cw - c.width) // 2, y0 + (ch - c.height) // 2))
            d.rectangle((x0, y0, x0 + cw, y0 + ch), outline="#cbd5e1", width=2)
        pages.append(page)
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", resolution=300, save_all=True, append_images=pages[1:])
    return buf.getvalue()

```
