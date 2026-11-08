"""Dimensioned 2D drawings of the door enclosure, generated from the SAME params.json the SOLIDWORKS
build uses (standard library only). Writes out/DoorEnclosure_Drawings.html (one A4 sheet per view);
frontend/e2e/dossier_pdf.mjs turns it into the PDF:
    py -I tools/cad/door_enclosure/drawings.py
    cd frontend && node e2e/dossier_pdf.mjs ../tools/cad/door_enclosure/out/DoorEnclosure_Drawings.html ../tools/cad/door_enclosure/out/DoorEnclosure_Drawings.pdf
All dimensions in mm. Views are true scale inside each sheet (scale printed in the title block).
"""
from __future__ import annotations

import datetime
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(os.path.join(HERE, "params.json"), encoding="utf-8"))
E, FP, F, EP = P["envelope"], P["front_panel"], P["fasteners"], P["electronics_plate"]
W, H, D, T = E["width"], E["height"], E["depth"], E["wall"]


class Svg:
    """Drawing in model mm, y up; converted to SVG (y down) on output."""

    def __init__(self, x0, y0, x1, y1):
        self.b = (x0, y0, x1, y1)
        self.el: list[str] = []

    def Y(self, y):
        return self.b[3] + self.b[1] - y

    def rect(self, cx, cy, w, h, cls="cut", r=0):
        self.el.append(f'<rect class="{cls}" x="{cx - w / 2:.2f}" y="{self.Y(cy + h / 2):.2f}" width="{w:.2f}" height="{h:.2f}" rx="{r}"/>')

    def circ(self, cx, cy, d, cls="cut"):
        self.el.append(f'<circle class="{cls}" cx="{cx:.2f}" cy="{self.Y(cy):.2f}" r="{d / 2:.2f}"/>')

    def line(self, x1, y1, x2, y2, cls="thin"):
        self.el.append(f'<line class="{cls}" x1="{x1:.2f}" y1="{self.Y(y1):.2f}" x2="{x2:.2f}" y2="{self.Y(y2):.2f}"/>')

    def text(self, x, y, s, size=3.0, anchor="middle", cls="lbl", rot=0):
        tr = f' transform="rotate({rot} {x:.2f} {self.Y(y):.2f})"' if rot else ""
        self.el.append(f'<text class="{cls}" x="{x:.2f}" y="{self.Y(y):.2f}" font-size="{size}" text-anchor="{anchor}"{tr}>{html.escape(s)}</text>')

    def hdim(self, x1, x2, y, ref_y, label=None):
        """horizontal dimension between x1..x2 drawn at height y, extension lines from ref_y"""
        for x in (x1, x2):
            self.line(x, ref_y, x, y + (1.5 if y > ref_y else -1.5), "ext")
        self.el.append(f'<line class="dim" x1="{x1:.2f}" y1="{self.Y(y):.2f}" x2="{x2:.2f}" y2="{self.Y(y):.2f}" marker-start="url(#a)" marker-end="url(#a)"/>')
        self.text((x1 + x2) / 2, y + 0.9, label or f"{abs(x2 - x1):g}", 3.2, cls="dimt")

    def vdim(self, y1, y2, x, ref_x, label=None):
        for y in (y1, y2):
            self.line(ref_x, y, x + (1.5 if x > ref_x else -1.5), y, "ext")
        self.el.append(f'<line class="dim" x1="{x:.2f}" y1="{self.Y(y1):.2f}" x2="{x:.2f}" y2="{self.Y(y2):.2f}" marker-start="url(#a)" marker-end="url(#a)"/>')
        self.text(x - 0.9, (y1 + y2) / 2, label or f"{abs(y2 - y1):g}", 3.2, cls="dimt", rot=-90)

    def leader(self, x, y, tx, ty, s, anchor="start"):
        self.line(x, y, tx, ty, "lead")
        self.text(tx + (1 if anchor == "start" else -1), ty - 1, s, 3.3, anchor=anchor, cls="note")

    def svg(self, width_mm):
        x0, y0, x1, y1 = self.b
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {x1 - x0} {y1 - y0}" style="width:{width_mm}mm">'
                '<defs><marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
                '<path d="M0,2 L10,5 L0,8 z" fill="#1d4ed8"/></marker></defs>' + "".join(self.el) + "</svg>")


def front_panel() -> Svg:
    s = Svg(-W / 2 - 100, -30, W / 2 + 100, H + 24)
    s.rect(0, H / 2, W, H, "outline", E["corner_radius"])
    ci = F["corner_boss_inset"]
    for x in (-W / 2 + ci, W / 2 - ci):
        for y in (ci, H - ci):
            s.circ(x, y, F["screw_clear_d"])
    s.leader(W / 2 - ci, H - ci, W / 2 + 6, H + 10, f"4x Ø{F['screw_clear_d']} thru (M3)")
    t, n, fg, ld, bz = P["tft"], P["nfc"], P["fingerprint"], P["leds"], P["buzzer"]
    # TFT: window + the PCB's 4 holes (bosses behind), PCB and glass outlines dashed
    s.rect(t["center_x"], t["center_y"], t["pcb_w"], t["pcb_h"], "hidden")
    s.rect(t["center_x"], t["center_y"], t["glass_w"], t["glass_h"], "hidden")
    s.rect(t["center_x"], t["center_y"] + t["window_offset_y"], t["window_w"], t["window_h"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            s.circ(t["center_x"] + sx * t["hole_dx"] / 2, t["center_y"] + sy * t["hole_dy"] / 2, t["boss_d"], "hidden")
            s.circ(t["center_x"] + sx * t["hole_dx"] / 2, t["center_y"] + sy * t["hole_dy"] / 2, F["pilot_m25_d"], "hidden")
    s.leader(t["center_x"] + t["window_w"] / 2, t["center_y"] + 12, W / 2 + 6, t["center_y"] + 30,
             f"TFT window {t['window_w']:g} x {t['window_h']:g} thru")
    s.leader(t["center_x"] + t["hole_dx"] / 2, t["center_y"] - t["hole_dy"] / 2, W / 2 + 6, t["center_y"] - 22,
             f"4x boss Ø{t['boss_d']:g} x {t['boss_h']:g} on {t['hole_dx']:g} x {t['hole_dy']:g}, pilot Ø{F['pilot_m25_d']:g} x {t['pilot_depth']:g}")
    s.hdim(t["center_x"] - t["hole_dx"] / 2, t["center_x"] + t["hole_dx"] / 2, t["center_y"] + t["hole_dy"] / 2 + 6, t["center_y"] + t["hole_dy"] / 2)
    s.vdim(t["center_y"] - t["hole_dy"] / 2, t["center_y"] + t["hole_dy"] / 2, t["center_x"] + t["pcb_w"] / 2 + 5, t["center_x"] + t["hole_dx"] / 2)
    # NFC: rear pocket with 4 islands
    s.rect(n["center_x"], n["center_y"], n["pocket_w"], n["pocket_h"], "hidden")
    for sx in (-1, 1):
        for sy in (-1, 1):
            s.circ(n["center_x"] + sx * n["island_dx"] / 2, n["center_y"] + sy * n["island_dy"] / 2, n["island_d"], "hidden")
    m = n["tap_outline_margin"] + n["tap_outline_groove"] / 2
    s.rect(n["center_x"], n["center_y"], n["pocket_w"] + 2 * m, n["pocket_h"] + 2 * m, "engr")
    s.leader(n["center_x"] - n["pocket_w"] / 2, n["center_y"] + 14, -W / 2 - 4, n["center_y"] + 34,
             f"rear pocket {n['pocket_w']:g} x {n['pocket_h']:g} x {n['pocket_depth']:g} (skin {n['front_skin']:g})", "end")
    s.leader(n["center_x"] - n["island_dx"] / 2, n["center_y"] - n["island_dy"] / 2, -W / 2 - 4, n["center_y"] - 30,
             f"4x island Ø{n['island_d']:g} on {n['island_dx']:g} x {n['island_dy']:g}, pilot Ø{F['pilot_m25_d']:g} x {n['pilot_depth']:g}", "end")
    # fingerprint: pocket + aperture at the sensor end
    sgn = -1 if fg["sensor_end"] == "left" else 1
    ax = fg["center_x"] + sgn * (fg["body_l"] / 2 - fg["aperture_l"] / 2)
    s.rect(fg["center_x"], fg["center_y"], fg["pocket_l"], fg["pocket_w"], "hidden")
    s.rect(fg["center_x"], fg["center_y"], fg["pocket_l"] + 2 * fg["cradle_wall"], fg["pocket_w"] + 2 * fg["cradle_wall"], "hidden")
    s.rect(ax, fg["center_y"], fg["aperture_l"], fg["aperture_w"])
    s.leader(ax + fg["aperture_l"] / 2, fg["center_y"] + 4, W / 2 + 6, fg["center_y"] + 14,
             f"FP aperture {fg['aperture_l']:g} x {fg['aperture_w']:g} thru (sensor end {fg['sensor_end']})")
    s.leader(fg["center_x"] + fg["pocket_l"] / 2, fg["center_y"] - 6, W / 2 + 6, fg["center_y"] - 8,
             f"pocket {fg['pocket_l']:g} x {fg['pocket_w']:g} x {fg['pocket_depth']:g}; cradle h {fg['cradle_h']:g} + tie slots")
    s.hdim(fg["center_x"] - fg["pocket_l"] / 2, ax + fg["aperture_l"] / 2, fg["center_y"] + 18, fg["center_y"])
    # LEDs + buzzer
    d = ld["holder_d"] if ld["use_holder"] else ld["bare_d"]
    for x in (ld["green_x"], ld["red_x"]):
        s.circ(x, ld["y"], d)
    s.leader(ld["red_x"], ld["y"], W / 2 + 6, ld["y"] + 6, f"2x Ø{d:g} LED")
    import math
    s.circ(bz["center_x"], bz["center_y"], bz["sound_hole_d"])
    for i in range(6):
        a = i * math.pi / 3
        s.circ(bz["center_x"] + bz["sound_ring_d"] / 2 * math.cos(a), bz["center_y"] + bz["sound_ring_d"] / 2 * math.sin(a), bz["sound_hole_d"])
    s.circ(bz["center_x"], bz["center_y"], bz["cradle_id"], "hidden")
    s.circ(bz["center_x"], bz["center_y"], bz["cradle_id"] + 2 * bz["cradle_wall"], "hidden")
    s.leader(bz["center_x"] + 4, bz["center_y"], W / 2 + 6, bz["center_y"] - 8,
             f"7x Ø{bz['sound_hole_d']:g} on Ø{bz['sound_ring_d']:g}; rear cradle ID {bz['cradle_id']:g} x {bz['cradle_h']:g}")
    s.text(0, FP["title_y"] - FP["title_height"], FP["title"], FP["title_height"], cls="engrt")
    th = FP["text_height"]
    s.text(n["center_x"], n["center_y"] - n["pocket_h"] / 2 - n["tap_outline_margin"] - n["tap_outline_groove"] - th - 2.5, "TAP CARD", th, cls="engrt")
    s.text(fg["center_x"], fg["center_y"] - fg["pocket_w"] / 2 - th - 4, "FINGER", th, cls="engrt")
    s.text(ld["green_x"], ld["y"] - ld["bare_d"] / 2 - th - 2.5, "OK", th, cls="engrt")
    s.text(ld["red_x"], ld["y"] - ld["bare_d"] / 2 - th - 2.5, "DENIED", th, cls="engrt")
    # positions (from the bottom-left datum = panel corner)
    s.hdim(-W / 2, W / 2, -12, 0)
    s.vdim(0, H, -W / 2 - 12, -W / 2)
    for (x, y, lab) in ((t["center_x"], t["center_y"], "TFT"), (n["center_x"], n["center_y"], "NFC"),
                        (fg["center_x"], fg["center_y"], "FP"), (ld["green_x"], ld["y"], "LED"), (bz["center_x"], bz["center_y"], "BZ")):
        s.line(x - 2, y, x + 2, y, "ctr"); s.line(x, y - 2, x, y + 2, "ctr")
    s.vdim(0, t["center_y"], -W / 2 - 24, -W / 2, f"{t['center_y']:g}")
    s.vdim(0, n["center_y"], -W / 2 - 5, -W / 2 + 4, f"{n['center_y']:g}")
    s.vdim(0, ld["y"], W / 2 + 4, W / 2, f"{ld['y']:g}")
    s.vdim(0, bz["center_y"], W / 2 + 12, W / 2, f"{bz['center_y']:g}")
    s.hdim(0, n["center_x"], -22, 0, f"{abs(n['center_x']):g}")
    s.hdim(0, fg["center_x"], -22, 0, f"{fg['center_x']:g}")
    s.hdim(ld["green_x"], ld["red_x"], ld["y"] - 12, ld["y"])
    return s


def body_bottom() -> Svg:
    """Bottom wall seen from below: gland holes (x from the centre, z from the back face)."""
    s = Svg(-W / 2 - 22, -22, W / 2 + 40, D + 18)
    s.rect(0, D / 2, W, D, "outline", 0)
    g = P["glands"]
    for h in g["holes"]:
        s.circ(h["x"], g["z"], h["d"])
        s.text(h["x"], g["z"] + h["d"] / 2 + 2.5, f"Ø{h['d']:g} {h['name']}", 3.0, cls="note")
        s.line(h["x"], g["z"] - 3, h["x"], g["z"] + 3, "ctr")
    s.hdim(-W / 2, W / 2, -10, 0)
    s.vdim(0, D, -W / 2 - 10, -W / 2)
    s.vdim(0, g["z"], W / 2 + 8, W / 2, f"{g['z']:g}")
    xs = sorted(h["x"] for h in g["holes"])
    for a, b in zip([0] + xs[:-1], xs):
        pass
    s.hdim(xs[0], xs[-1], -18, 0)
    for x in xs:
        s.text(x, g["z"] - 13, f"x={x:g}", 3.0, cls="dimt")
    s.text(0, D + 8, "BOTTOM WALL from below (back face at the top edge = wall side, z = 0)", 3, cls="note")
    return s


def body_left() -> Svg:
    """Left wall seen from outside: USB opening and vents (y from the bottom, z from the back face)."""
    s = Svg(-24, -22, D + 62, H + 14)
    s.rect(D / 2, H / 2, D, H, "outline", 0)
    u, v = P["usb_access"], P["vents"]
    s.rect(u["z"], u["y"], u["w"] if False else u["h"], u["w"])     # opening: h along z, w along y
    s.leader(u["z"] + u["h"] / 2, u["y"], D + 4, u["y"] + 10, f"USB {u['w']:g} (y) x {u['h']:g} (z)")
    for y in v["y_list"]:
        s.rect((v["z_from"] + v["z_to"]) / 2, y, v["z_to"] - v["z_from"] + v["slot_h"], v["slot_h"], "cut", v["slot_h"] / 2)
    s.leader(v["z_to"], v["y_list"][-1], D + 4, H + 4, f"{len(v['y_list'])} vent slots {v['slot_h']:g} wide, both side walls")
    s.hdim(0, D, -10, 0)
    s.vdim(0, H, -10, 0)
    s.vdim(0, u["y"], D + 8 + 10, D, f"{u['y']:g}")
    s.hdim(0, u["z"], -18, 0, f"{u['z']:g}")
    s.text(D / 2, H + 7, "LEFT WALL from outside (z = 0 = wall side)", 3, cls="note")
    return s


def plate() -> Svg:
    pw, py0, py1 = W - 2 * EP["x_margin"], EP["y_bottom"], H - EP["y_top_margin"]
    s = Svg(-W / 2 - 22, py0 - 24, W / 2 + 22, py1 + 14)
    s.rect(0, (py0 + py1) / 2, W, H, "hidden")
    s.rect(0, (py0 + py1) / 2, pw, py1 - py0, "outline", 4)
    hi = EP["hole_inset"]
    for x in (-pw / 2 + hi, pw / 2 - hi):
        for y in (py0 + hi, py1 - hi):
            s.circ(x, y, F["screw_clear_d"])
    for c in P["components"]:
        if c.get("on") != "plate":
            continue
        s.rect(c["x"], c["y"], c["w"], c["h"], "comp")
        s.text(c["x"], c["y"] + 1, c["label"], 2.6, cls="note")
        s.text(c["x"], c["y"] - 3, f"{c['w']:g} x {c['h']:g} x {c['d']:g}", 2.2, cls="dimt")
    s.hdim(-pw / 2, pw / 2, py0 - 10, py0)
    s.vdim(py0, py1, -pw / 2 - 10, -pw / 2)
    s.hdim(-pw / 2 + hi, pw / 2 - hi, py0 - 18, py0 + hi)
    s.text(0, py1 + 7, "ELECTRONICS PLATE - component envelopes (incl. clearance), y from the box bottom", 3, cls="note")
    return s


CSS = """
@page { size: A4 landscape; margin: 10mm }
body { font-family: 'Segoe UI', Arial, sans-serif; color: #111; margin: 0 }
.sheet { page-break-after: always; display: grid; grid-template-rows: auto 1fr auto; height: 186mm }
h1 { font-size: 13pt; margin: 0 0 2mm } h2 { font-size: 10pt; margin: 0; color: #444; font-weight: 500 }
.views { display: flex; gap: 6mm; align-items: center; justify-content: center }
.tb { display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; border: .4mm solid #111; font-size: 7.5pt }
.tb div { border-left: .2mm solid #999; padding: 1mm 2mm } .tb div:first-child { border-left: 0 }
svg .outline { fill: #f8fafc; stroke: #111; stroke-width: .45 } svg .cut { fill: #fff; stroke: #111; stroke-width: .35 }
svg .hidden { fill: none; stroke: #666; stroke-width: .25; stroke-dasharray: 1.5 1 } svg .engr { fill: none; stroke: #7c3aed; stroke-width: .4 }
svg .comp { fill: #dbeafe; stroke: #1e40af; stroke-width: .3 } svg .thin, svg .ext { stroke: #1d4ed8; stroke-width: .15 }
svg .dim { stroke: #1d4ed8; stroke-width: .2 } svg .lead { stroke: #555; stroke-width: .18 } svg .ctr { stroke: #b91c1c; stroke-width: .15 }
svg text { font-family: 'Segoe UI', Arial, sans-serif } svg .dimt { fill: #1d4ed8 } svg .note { fill: #333 } svg .engrt { fill: #7c3aed; font-weight: 700 }
table { border-collapse: collapse; font-size: 7.5pt; width: 100% } td, th { border: .2mm solid #bbb; padding: .6mm 1.5mm; text-align: left }
"""


def sheet(title, sub, views, scale, n, total, extra=""):
    today = datetime.date.today().isoformat()
    return (f'<section class="sheet"><div><h1>{html.escape(title)}</h1><h2>{html.escape(sub)}</h2></div>'
            f'<div class="views">{views}</div>{extra}'
            f'<div class="tb"><div><b>ALIoT Smart Lab - MASTER_LAB01 door node enclosure</b><br>source: tools/cad/door_enclosure/params.json + Build.cs (SOLIDWORKS 2025)</div>'
            f'<div>units mm<br>general tol. ±0.3 (FDM)</div><div>scale {scale}<br>{today}</div><div>sheet {n} / {total}<br>status: FIT-TEST RELEASE</div></div></section>')


def main():
    comps = "".join(
        f"<tr><td>{html.escape(c['label'])}</td><td>{c['w']:g} x {c['h']:g} x {c['d']:g}</td><td>{c['x']:g}, {c['y']:g}, z {c['z']:g} {c.get('dir', 'up')}</td>"
        f"<td>{html.escape(c.get('conf', ''))}</td><td>{html.escape(c.get('src', ''))}</td></tr>" for c in P["components"])
    table = ('<table><tr><th>Envelope</th><th>w x h x d (incl. clearance)</th><th>centre x, y; base z</th><th>confidence</th><th>source</th></tr>'
             + comps + "</table>")
    sheets = [
        ("Front panel - front view", "seen from the corridor; dashed = rear features (pockets, bosses, cradles); purple = engraved", front_panel().svg(205), "≈1:1.8"),
        ("Body - bottom wall and left wall", "cable entries (bottom) and ESP32 USB access + vents (left)", body_bottom().svg(135) + body_left().svg(110), "≈1:1.6"),
        ("Electronics plate - layout", "component envelopes as used in the SOLIDWORKS interference check", plate().svg(150), "≈1:1.3"),
    ]
    total = len(sheets) + 1
    body = "".join(sheet(t, s, v, sc, i + 1, total) for i, (t, s, v, sc) in enumerate(sheets))
    body += sheet("Component envelopes", "every box in the virtual assembly, with where its size comes from", "", "-", total, total, table)
    out = os.path.join(HERE, "out", "DoorEnclosure_Drawings.html")
    open(out, "w", encoding="utf-8").write(f"<!doctype html><html><head><meta charset='utf-8'><title>Door enclosure drawings</title><style>{CSS}</style></head><body>{body}</body></html>")
    print("wrote", out)


if __name__ == "__main__":
    main()
