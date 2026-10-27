"""
Owner's QR marker pack (2026-10-27, "smart_lab_qr_ready"): the category motif is drawn by RECOLOURING real dark
modules of a standard QR (version >= 5, error correction H, 4-module quiet zone) - no module deleted, nothing laid
over the code. The renderer below is the pack's generate_markers.py, ported unchanged (same masks, colours,
finder handling and module insets), but fed with the payloads of the REAL registry (scan.registry), never with the
pack's caption guesses.

Payload check of the pack (2026-10-27, against scan.registry): 6 of 8 exact - CAM_LAB01, FACESRV_01, MASTER_LAB01,
PC_ADMIN_LAPTOP, UR5E_01, FANUC_01 - their files are used as supplied (backend/data/marker_pack, verified.json).
Two did not exist: SLAB:D:CONS_BIN_01 (real: SLAB:D:BIN_NODE_1 / SLAB:B:BIN-R10K) and SLAB:D:SEC_NODE_01 (real:
SLAB:D:SECCAM_LAB01 / _LAB02) - not used; those assets (and every other registered one) are rendered here from
their real payload. Every marker is decoded back before it is served; one that does not read is served as a
plain QR.
"""
from __future__ import annotations

import functools
import io
import json
import os
from typing import Optional

import qrcode
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_H

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "marker_pack")
BASE = (13, 25, 43)                 # #0d192b
# the pack's category colours and shapes
CATS = {"camera": ("#6426a8", "camera", "CAMERA"), "server": ("#562099", "server", "SERVER"),
        "door": ("#075f59", "door", "DOOR"), "pc": ("#1557ad", "laptop", "PC"), "robot": ("#b84300", "robot", "ROBOT"),
        "inventory": ("#976000", "bin", "INVENTORY"), "security": ("#a71f31", "shield", "SECURITY"),
        "reusable": ("#0e6e83", "bin", "REUSABLES"), "environment": ("#15803d", "server", "ENVIRONMENT"),
        "equipment": ("#334155", None, "EQUIPMENT")}
TYPE_CAT = {"Entry camera": "camera", "Face server": "server", "Door controller (master ESP32)": "door",
            "Lab PC": "pc", "Robot": "robot", "Manipulator": "robot", "Consumables bin node": "inventory",
            "Consumables bin": "inventory", "Security camera": "security", "Access control": "security",
            "Reusable-items bin node": "reusable", "Reusable-bin item": "reusable", "Environment node": "environment"}


def category(item: dict) -> str:
    return TYPE_CAT.get(item.get("type") or "", "equipment")


def _rgb(hexs: str) -> tuple:
    return tuple(int(hexs[i:i + 2], 16) for i in (1, 3, 5))


# ------------------------------------------------------------------------------- the pack's renderer ---
def shape_mask(shape: Optional[str], w: int, h: int) -> Image.Image:
    im = Image.new("L", (w, h), 0)
    if shape is None:
        return im
    d = ImageDraw.Draw(im)
    unit = min(w, h)
    stroke = max(3, int(unit * 0.105))
    fine = max(2, int(unit * 0.065))

    def xy(box):
        x1, y1, x2, y2 = box
        return (int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h))

    def outline_rect(box, radius=0, width=stroke):
        if radius:
            d.rounded_rectangle(xy(box), radius=int(radius * unit), outline=255, width=width)
        else:
            d.rectangle(xy(box), outline=255, width=width)

    def outline_ellipse(box, width=stroke):
        d.ellipse(xy(box), outline=255, width=width)

    def line(points, width=stroke):
        d.line([(int(x * w), int(y * h)) for x, y in points], fill=255, width=width, joint="curve")

    def poly_outline(points, width=stroke):
        pts = [(int(x * w), int(y * h)) for x, y in points]
        d.line(pts + [pts[0]], fill=255, width=width, joint="curve")
    if shape == "camera":
        outline_rect((.17, .31, .83, .75), .07, stroke)
        line([(.31, .31), (.39, .21), (.61, .21), (.69, .31)], stroke)
        outline_ellipse((.39, .38, .63, .68), stroke)
        outline_ellipse((.44, .43, .58, .63), fine)
        outline_rect((.73, .23, .83, .29), .02, fine)
    elif shape == "server":
        outline_rect((.20, .16, .80, .31), .03, stroke)
        outline_rect((.20, .425, .80, .575), .03, stroke)
        outline_rect((.20, .69, .80, .84), .03, stroke)
        for cy in (.235, .50, .765):
            outline_ellipse((.69, cy - .025, .74, cy + .025), fine)
    elif shape == "door":
        line([(.23, .88), (.23, .13), (.77, .13), (.77, .88)], stroke)
        line([(.32, .86), (.32, .24), (.69, .24), (.69, .86)], fine)
        line([(.60, .48), (.60, .60)], stroke)
        outline_ellipse((.575, .51, .625, .56), fine)
    elif shape == "laptop":
        outline_rect((.24, .18, .76, .68), .015, stroke)
        line([(.17, .73), (.83, .73), (.90, .83), (.10, .83), (.17, .73)], stroke)
        line([(.42, .76), (.58, .76)], fine)
    elif shape == "robot":
        line([(.20, .80), (.46, .80), (.46, .62), (.34, .48), (.56, .31), (.75, .43), (.82, .27)], stroke + 1)
        for cx, cy, r in ((.46, .62, .075), (.34, .48, .065), (.56, .31, .065), (.75, .43, .06), (.82, .27, .05)):
            outline_ellipse((cx - r, cy - r, cx + r, cy + r), stroke)
        line([(.76, .27), (.86, .27)], fine)
    elif shape == "bin":
        poly_outline([(.20, .31), (.80, .31), (.74, .82), (.26, .82)], stroke)
        line([(.16, .30), (.16, .23), (.84, .23), (.84, .30)], stroke)
        line([(.42, .18), (.42, .12), (.58, .12), (.58, .18)], fine)
        for x in (.37, .50, .63):
            line([(x, .40), (x, .70)], fine)
    elif shape == "shield":
        poly_outline([(.50, .13), (.81, .25), (.77, .59), (.66, .79), (.50, .88), (.34, .79), (.23, .59), (.19, .25)], stroke)
        outline_rect((.39, .49, .61, .65), .025, fine)
        line([(.43, .49), (.43, .44), (.46, .40), (.54, .40), (.57, .44), (.57, .49)], fine)
    return im


def is_finder_function(x: int, y: int, size: int) -> bool:
    b = 4
    return ((b <= x < b + 9 and b <= y < b + 9) or (size - b - 9 <= x < size - b and b <= y < b + 9)
            or (b <= x < b + 9 and size - b - 9 <= y < size - b))


def _matrix(payload: str) -> list:
    qr = qrcode.QRCode(version=5, error_correction=ERROR_CORRECT_H, box_size=16, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.get_matrix()


def _cells(payload: str, cat: str, art: bool):
    color, shape, _ = CATS[cat]
    m = _matrix(payload)
    n = len(m)
    sp = shape_mask(shape if art else None, n, n).load()
    for y, row in enumerate(m):
        for x, dark in enumerate(row):
            if dark:
                finder = is_finder_function(x, y, n)
                yield x, y, n, (color if sp[x, y] > 0 and not finder else "#0d192b"), finder


def render_png(payload: str, cat: str, cell: int = 16, art: bool = True) -> Image.Image:
    m = _matrix(payload)
    n = len(m)
    img = Image.new("RGB", (n * cell, n * cell), "white")
    d = ImageDraw.Draw(img)
    for x, y, _, color, finder in _cells(payload, cat, art):
        inset = 0 if finder else max(1, cell // 10)
        d.rectangle((x * cell + inset, y * cell + inset, (x + 1) * cell - inset - 1, (y + 1) * cell - inset - 1), fill=_rgb(color))
    return img


def render_svg(payload: str, cat: str, cell: int = 16, art: bool = True) -> str:
    n = len(_matrix(payload))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{n * cell}" height="{n * cell}" viewBox="0 0 {n * cell} {n * cell}" '
           f'shape-rendering="crispEdges">', '<rect width="100%" height="100%" fill="#ffffff"/>']
    for x, y, _, color, finder in _cells(payload, cat, art):
        inset = 0 if finder else max(1, cell // 10)
        out.append(f'<rect x="{x * cell + inset}" y="{y * cell + inset}" width="{cell - 2 * inset}" height="{cell - 2 * inset}" fill="{color}"/>')
    out.append("</svg>")
    return "\n".join(out)


# ------------------------------------------------------------------------- verified pack files ---
@functools.lru_cache(maxsize=1)
def verified() -> dict:
    """{payload: slug} of the pack files whose payload matched the registry (backend/data/marker_pack/verified.json)."""
    p = os.path.join(DATA, "verified.json")
    if not os.path.isfile(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return {a["payload"]: a["slug"] for a in json.load(f)["verified"]}


def decodes(img: Image.Image, code: str) -> bool:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return True
    det = cv2.QRCodeDetector()
    ok = 0
    for size in (img.width, 480, 320, 240):
        a = img if size == img.width else img.resize((size, size), Image.LANCZOS)
        ok += det.detectAndDecode(np.array(a.convert("RGB"))[:, :, ::-1])[0] == code
    return ok >= 3


@functools.lru_cache(maxsize=256)
def qr_png(code: str, cat: str) -> tuple[bytes, str]:
    """(PNG of the QR alone, source): 'pack' file as supplied, 'generated' in the pack style, or 'plain'."""
    slug = verified().get(code)
    if slug:
        p = os.path.join(DATA, f"{slug}.png")
        if os.path.isfile(p):
            img = Image.open(p).convert("RGB")
            if decodes(img, code):
                with open(p, "rb") as f:
                    return f.read(), "pack"
    img, src = render_png(code, cat), "generated"
    if not decodes(img, code):
        img, src = render_png(code, cat, art=False), "plain"
    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(300, 300), optimize=True)
    return buf.getvalue(), src


@functools.lru_cache(maxsize=256)
def qr_svg(code: str, cat: str) -> str:
    slug = verified().get(code)
    if slug and qr_png(code, cat)[1] == "pack":
        p = os.path.join(DATA, f"{slug}.svg")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                return f.read()
    return render_svg(code, cat, art=qr_png(code, cat)[1] != "plain")


def _font(px, bold=True):
    for f in (("DejaVuSans-Bold.ttf", "arialbd.ttf") if bold else ("DejaVuSans.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(f, px)
        except OSError:
            continue
    return ImageFont.load_default(px)


def card_png(item: dict, width: int = 760) -> bytes:
    """The pack's printable card: white, rounded light outline, category-colour top edge, the QR, name and
    'ID  ·  CATEGORY' in the category colour."""
    cat = category(item)
    color = _rgb(CATS[cat][0])
    qr = Image.open(io.BytesIO(qr_png(item["code"], cat)[0])).convert("RGB")
    size = int(width * 0.86)
    qr = qr.resize((size, size), Image.NEAREST)
    H = size + int(width * 0.2)
    c = Image.new("RGB", (width, H), "white")
    d = ImageDraw.Draw(c)
    d.rounded_rectangle((0, 0, width - 1, H - 1), radius=24, outline=(220, 227, 236), width=3, fill="white")
    d.rounded_rectangle((0, 0, width - 1, 12), radius=6, fill=color)
    c.paste(qr, ((width - size) // 2, 18))
    name = (item.get("name") or "")[:40]
    y = 18 + size + 6
    f = _font(int(width * 0.04))
    while d.textlength(name, font=f) > width - 40 and f.size > 14:
        f = _font(f.size - 1)
    d.text((width / 2, y), name, font=f, fill=(19, 35, 58), anchor="mt")
    key = item["code"].split(":", 2)[-1]
    ident = f"{key}  ·  {CATS[cat][2]}" + (f"  ·  {item['lab_code']}" if item.get("lab_code") else "")
    d.text((width / 2, y + int(width * 0.06)), ident, font=_font(int(width * 0.026), bold=False), fill=color, anchor="mt")
    buf = io.BytesIO()
    c.save(buf, "PNG", dpi=(300, 300), optimize=True)
    return buf.getvalue()


def sheet_pdf(items: list[dict], cols: int = 2, rows: int = 4) -> bytes:
    """A4 at 300 dpi in the pack's sheet layout (2 x 4 cards)."""
    PW, PH, mx, top, gx, gy = 2480, 3508, 80, 120, 55, 25
    cw = (PW - 2 * mx - gx) // cols
    ch = (PH - top - 80 - (rows - 1) * gy) // rows
    pages = []
    for start in range(0, max(1, len(items)), cols * rows):
        page = Image.new("RGB", (PW, PH), "white")
        ImageDraw.Draw(page).text((mx, 40), "SMART LAB - ASSET QR MARKERS", font=_font(48), fill=(13, 25, 43))
        for k, it in enumerate(items[start:start + cols * rows]):
            card = Image.open(io.BytesIO(card_png(it, width=min(cw, int(ch / 1.2)))))
            x = mx + (k % cols) * (cw + gx) + (cw - card.width) // 2
            y = top + (k // cols) * (ch + gy)
            page.paste(card, (x, y))
        pages.append(page)
    buf = io.BytesIO()
    pages[0].save(buf, "PDF", resolution=300, save_all=True, append_images=pages[1:])
    return buf.getvalue()
