# Reusable-bin dock (2026-10-25): turns the traced bin outline (bin_outline_mm.json) into the 2D profiles the
# SOLIDWORKS builder extrudes, and writes params.json. Offsets are done on a 0.1 mm raster (distance transform),
# so every profile is the outline grown / shrunk by an exact amount. Run: py -I gen_params.py
#
# Frames. Bin (trace): x back -> front (pedal at +x), y right -> left (owner "Left" at +y).
# Tray / assembly: X = x - 100, Z = y - 150, Y up (0 = floor). Box: xb = x - BOX_CX, zb = y - y0 (out of the
# bin's left side), yb up from the box bottom (= floor + tongue). Sketches on the Top Plane use (X, -Z).
import json, math, os
import numpy as np, cv2

HERE = os.path.dirname(os.path.abspath(__file__))
R = 10                      # raster px per mm
OX, OY = -20.0, 20.0        # raster origin in bin mm
NX, NY = 260 * R, 320 * R

# ---- design numbers (mm) ----
CLR = 0.3                   # owner's rule: every fit = part + 0.3
POCKET = 1.5                # bin -> tray rim: the outline is a pen trace (+-1 mm), so 1.5, not 0.3
RIM_T, RIM_H = 2.4, 15.0    # tray rim wall, height above the floor
FLOOR = 3.0
FLOOR_RING = 20.0           # floor kept 20 mm in from the bin edge, the middle is open (lever channel stays free)
PEDAL_TOP = 13.0            # owner estimate: pedal top above the floor the bin stands on
COVER_GAP = 12.0            # free space above the pedal under the cover
COVER_T = 2.5
SADDLE_GAP = 2.5            # box's curved face -> bin wall
SADDLE_MAX = 25.0           # deepest the curved face reaches toward the bin
BOX_CX = 90.0               # box centre along the bin (x)
TONGUE_T = FLOOR

def mm2px(x, y): return int(round((x - OX) * R)), int(round((y - OY) * R))
def raster(poly):
    m = np.zeros((NY, NX), np.uint8)
    cv2.fillPoly(m, [np.array([mm2px(x, y) for x, y in poly], np.int32)], 255)
    return m
def grow(m, d):             # d > 0 dilate, d < 0 erode, by an exact distance
    if d >= 0:
        dist = cv2.distanceTransform(255 - m, cv2.DIST_L2, 5) / R
        return np.where(dist <= d, 255, 0).astype(np.uint8)
    dist = cv2.distanceTransform(m, cv2.DIST_L2, 5) / R
    return np.where(dist > -d, 255, 0).astype(np.uint8)
def loops(m, eps=0.12):
    """Outer and hole loops of a mask, in tray coordinates (X, Z), simplified to eps mm."""
    cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cs:
        if cv2.contourArea(c) < 4 * R * R: continue
        a = cv2.approxPolyDP(c, eps * R, True).reshape(-1, 2)
        out.append([[round(px / R + OX - 100, 2), round(py / R + OY - 150, 2)] for px, py in a])
    return out
def rect_mask(x0, x1, y0, y1):
    m = np.zeros((NY, NX), np.uint8)
    a, b = mm2px(x0, y0); c, d = mm2px(x1, y1); m[min(b, d):max(b, d), min(a, c):max(a, c)] = 255; return m
def disc_mask(x, y, d):
    m = np.zeros((NY, NX), np.uint8); cv2.circle(m, mm2px(x, y), int(round(d / 2 * R)), 255, -1); return m

pts = json.load(open(os.path.join(HERE, "bin_outline_mm.json")))["points"]
P = np.array(pts)
yy, xx = np.mgrid[0:NY, 0:NX]; X = xx / R + OX; Y = yy / R + OY

# ---- clean bin shape from the hand trace (owner: the pen wobbles, the real bin is a smooth curve) ----
# The pen line runs PEN mm outside the base. Body = a smooth closed curve (low-order Fourier fit of r(angle) through
# every trace point that is not the pedal or the rod-channel foot) cut by the straight back, corners rounded.
# Pedal and rod-channel foot are rebuilt from the owner's caliper numbers, placed where the trace shows them.
PEN = 0.0                                     # 0: with it the depth is 143.6 = the caliper 143.64 (owner)
PEDAL_W, PEDAL_OUT, CHANNEL_W = 56.6, 22.53, 33.24          # caliper (owner)
back_x = 27.6 + PEN                                           # the flat back (trace)
ped = (P[:, 0] > 165) & (P[:, 1] > 110) & (P[:, 1] < 180)    # pedal bump points
ntc = P[:, 0] < back_x + 1.5                                  # back line + rod-channel foot points
fit = P[~ped & ~ntc]
c0 = fit.mean(0)
ang = np.arctan2(fit[:, 1] - c0[1], fit[:, 0] - c0[0]); rad = np.hypot(fit[:, 0] - c0[0], fit[:, 1] - c0[1])
ORDER = 6
def basis(a): return np.column_stack([np.ones_like(a)] + [f(k * a) for k in range(1, ORDER + 1) for f in (np.cos, np.sin)])
coef = np.linalg.lstsq(basis(ang), rad, rcond=None)[0]
resid = rad - basis(ang) @ coef
th = np.linspace(-math.pi, math.pi, 1440, endpoint=False); rr = basis(th) @ coef - PEN
curve = np.c_[c0[0] + rr * np.cos(th), c0[1] + rr * np.sin(th)]
curve[:, 0] = np.maximum(curve[:, 0], back_x)                # the straight back
hull = cv2.convexHull(np.float32(curve)).reshape(-1, 2)       # the bin is convex (a D): no dent where the fit is unsupported
body = raster(hull.tolist())
CORNER_R = 10.0                                               # rounded back corners (photos)
body = grow(grow(body, -CORNER_R), CORNER_R)                  # opening = round the convex corners only
body_tip = X[body > 0].max()
# pedal: owner's width, centred where the trace has it, front at the larger of (caliper reach, trace - pen)
pp = P[ped]; pc = (pp[:, 1].min() + pp[:, 1].max()) / 2
ped_front = max(body_tip + PEDAL_OUT, pp[:, 0].max() - PEN)
ped_y0, ped_y1, ped_x1 = pc - PEDAL_W / 2, pc + PEDAL_W / 2, ped_front
pedal = rect_mask(body_tip - 15, ped_front, ped_y0, ped_y1)
pedal = grow(grow(pedal, -6.0), 6.0)                          # rounded pad corners
pedal = cv2.bitwise_and(pedal, cv2.bitwise_not(body))
# rod-channel foot behind the back: owner's width, depth from the trace
nt = P[ntc & (P[:, 0] < back_x - 5)]; nc = (nt[:, 1].min() + nt[:, 1].max()) / 2
notch = rect_mask(nt[:, 0].min() + PEN, back_x + 1, nc - CHANNEL_W / 2, nc + CHANNEL_W / 2)
B = body | pedal | notch
band = (Y > ped_y0 - 5) & (Y < ped_y1 + 5) & (X > 150)

pocket = grow(B, POCKET)
rim_out = grow(B, POCKET + RIM_T)
ys, xs = np.nonzero(rim_out)
rim_ymax = ys.max() / R + OY

# ---- box position: back face 0.3 clear of the rim's outer face ----
left_max = Y[B > 0].max()
y0 = rim_ymax + CLR                                               # box back plane (bin y)
# tongues under the box's back edge, pegs into the box bottom
peg_zb, peg_d, peg_h = 7.0, 5.0, 2.8
tongue_w, tongue_y0, tongue_y1 = 20.0, rim_ymax - 3, y0 + 17.0
pegs_xb = [-50.0, 50.0]
tongues = np.zeros_like(B)
for xb in pegs_xb:
    c0, c1 = mm2px(BOX_CX + xb - tongue_w / 2, 0)[0], mm2px(BOX_CX + xb + tongue_w / 2, 0)[0]
    top = min(np.nonzero(rim_out[:, c])[0].max() for c in range(c0, c1)) / R + OY   # rim's outer edge under the tongue
    tongues |= rect_mask(BOX_CX + xb - tongue_w / 2, BOX_CX + xb + tongue_w / 2, top - 3, tongue_y1)

# ---- pedal hood (walls in the tray) and its screwed-on cover ----
hood_in_y0, hood_in_y1 = ped_y0 - POCKET, ped_y1 + POCKET
hood = rect_mask(150, 260, hood_in_y0 - RIM_T, hood_in_y1 + RIM_T) & rim_out
ear_d = 10.0
ex_ = ped_x1 - 12; hc = np.nonzero(hood[:, mm2px(ex_, 0)[0]])[0] / R + OY
ears = [(ex_, hc.min() - ear_d / 2 + 2.0), (ex_, hc.max() + ear_d / 2 - 2.0)]   # 2 mm into the hood wall
hood_walls = cv2.bitwise_and(hood, cv2.bitwise_not(pocket))
for ex, ey in ears: hood_walls |= disc_mask(ex, ey, ear_d)
floor = cv2.bitwise_and(rim_out | tongues | disc_mask(*ears[0], ear_d) | disc_mask(*ears[1], ear_d), cv2.bitwise_not(grow(body, -FLOOR_RING)))
cover = cv2.bitwise_and(hood, cv2.bitwise_not(grow(body, 2.0)))
for ex, ey in ears: cover |= disc_mask(ex, ey, ear_d)
y_floor_top = FLOOR
y_rim_top = FLOOR + RIM_H
y_cover = FLOOR + PEDAL_TOP + COVER_GAP

# ---- the box's curved face (box frame xb, zb; zb < 0 toward the bin) ----
S = grow(B, SADDLE_GAP)
sad = []
for xb in np.arange(-72, 72.01, 1.0):
    col = int(round((BOX_CX + xb - OX) * R)); ys_ = np.nonzero(S[:, col])[0]
    ymax = ys_.max() / R + OY if len(ys_) else -1e9
    sad.append([round(xb, 2), round(max(ymax - y0, -SADDLE_MAX), 2)])
saddle = [[-72.0, 1.5]] + sad + [[72.0, 1.5]]                     # closes 1.5 mm inside the 3 mm back wall

# ---- bin reference solid (for the interference check only, not printed) ----

def L(m, eps=0.12): return loops(m, eps)
TX, TZ = BOX_CX - 100, y0 - 150                                   # box origin in the tray frame
BOX_Y = 0.0                                                       # the box stands flat on the floor; the tongues go into pockets under it

prm = json.load(open(os.path.join(HERE, "params_base.json")))
prm["geometry"] = {
    "_about": "generated by gen_params.py from bin_outline_mm.json - do not edit by hand",
    "floor_t": FLOOR, "rim_top": y_rim_top, "cover_y": y_cover, "cover_t": COVER_T,
    "floor": L(floor), "rim": L(cv2.bitwise_and(rim_out, cv2.bitwise_not(pocket))), "hood_walls": L(hood_walls),
    "cover": L(cover), "ears": [[round(ex - 100, 2), round(ey - 150, 2)] for ex, ey in ears], "ear_d": ear_d,
    "pegs": [[round(BOX_CX + xb - 100, 2), round(y0 + peg_zb - 150, 2)] for xb in pegs_xb], "peg_d": peg_d, "peg_h": peg_h,
    "peg_zb": peg_zb, "pegs_xb": pegs_xb, "tongue_w": tongue_w, "tongue_zb": round(tongue_y1 - y0, 2), "tongue_t": TONGUE_T,
    "saddle": saddle, "saddle_from_y": round(y_rim_top - BOX_Y + 1.0, 2),
    "bin_body": L(body), "bin_notch": L(notch), "bin_pedal": L(pedal), "bin_h": 225.0,
    "pedal_top": FLOOR + PEDAL_TOP,
}
for part in ("Body", "Lid", "Plate"):
    pass
prm["assembly_parts"] = [
    {"name": "Tray", "x": 0, "y": 0, "z": 0}, {"name": "PedalCover", "x": 0, "y": 0, "z": 0},
    {"name": "BinReference", "x": 0, "y": 0, "z": 0},
    {"name": "Body", "x": round(TX, 2), "y": BOX_Y, "z": round(TZ, 2)},
    {"name": "Lid", "x": round(TX, 2), "y": BOX_Y, "z": round(TZ, 2)},
    {"name": "ElectronicsPlate", "x": round(TX, 2), "y": BOX_Y, "z": round(TZ, 2)}]
# component envelopes: given in the box frame in params_base, moved to the assembly frame here
for c in prm["components"]:
    c["x"] = round(c.pop("xb") + TX, 2); c["y"] = round(c.pop("yb") + BOX_Y, 2); c["z"] = round(c.pop("zb") + TZ, 2)
json.dump(prm, open(os.path.join(HERE, "params.json"), "w"), indent=1)

ext = lambda m: (lambda ys, xs: (xs.min() / R + OX, xs.max() / R + OX, ys.min() / R + OY, ys.max() / R + OY))(*np.nonzero(m))
fx0, fx1, fy0, fy1 = ext(floor)
print("fit: %d points, order %d, residual rms %.2f max %.2f mm; back x %.1f, tip x %.1f (depth %.1f); pedal y %.1f..%.1f to x %.1f; channel %.1f wide" % (len(fit), ORDER, resid.std(), abs(resid).max(), back_x, body_tip, body_tip - back_x, ped_y0, ped_y1, ped_x1, CHANNEL_W))
print("width max %.1f" % (Y[body > 0].max() - Y[body > 0].min()))
print("bin: x %.1f..%.1f  y %.1f..%.1f (left max %.1f)" % (*ext(B), left_max))
print("tray: %.1f x %.1f mm (x %.1f..%.1f, y %.1f..%.1f), cover top %.1f" % (fx1 - fx0, fy1 - fy0, fx0, fx1, fy0, fy1, y_cover + COVER_T))
print("box back plane y0 = %.2f (rim outer %.2f); box origin in tray frame X %.2f Z %.2f" % (y0, rim_ymax, TX, TZ))
print("saddle depth min/max %.1f / %.1f" % (-max(z for _, z in sad), -min(z for _, z in sad)))
for k in ("floor", "rim", "hood_walls", "cover", "bin_body", "bin_notch", "bin_pedal"):
    print(k, [len(l) for l in prm["geometry"][k]])
