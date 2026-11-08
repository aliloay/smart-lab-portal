"""Validate every exported STL in out/ (standard library only): size, triangle count, closed + manifold
(every edge shared by exactly two triangles), no degenerate triangles, consistent orientation and a
positive enclosed volume. Writes out/stl_check.json and prints one line per file; exit 1 on a failure.
    py -I tools/cad/door_enclosure/check_stl.py
"""
from __future__ import annotations

import json
import os
import struct
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def read_stl(path: str) -> list[tuple]:
    data = open(path, "rb").read()
    if len(data) >= 84:
        n = struct.unpack_from("<I", data, 80)[0]
        if 84 + 50 * n == len(data):
            tris = []
            for i in range(n):
                v = struct.unpack_from("<12f", data, 84 + 50 * i)
                tris.append((v[3:6], v[6:9], v[9:12]))
            return tris
    tris, cur = [], []
    for line in data.decode("ascii", "replace").splitlines():
        p = line.split()
        if p and p[0] == "vertex":
            cur.append(tuple(float(x) for x in p[1:4]))
            if len(cur) == 3:
                tris.append(tuple(cur)); cur = []
    return tris


def check(path: str) -> dict:
    tris = read_stl(path)
    q = lambda v: tuple(round(c, 5) for c in v)          # weld vertices (SOLIDWORKS writes them repeated)
    edges, directed = Counter(), Counter()
    degenerate, vol = 0, 0.0
    lo, hi = [1e9] * 3, [-1e9] * 3
    for a, b, c in tris:
        a, b, c = q(a), q(b), q(c)
        if a == b or b == c or a == c:
            degenerate += 1
            continue
        for e in ((a, b), (b, c), (c, a)):
            edges[frozenset(e)] += 1
            directed[e] += 1
        vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
        for v in (a, b, c):
            for k in range(3):
                lo[k], hi[k] = min(lo[k], v[k]), max(hi[k], v[k])
    open_edges = sum(1 for n in edges.values() if n == 1)
    nonmanifold = sum(1 for n in edges.values() if n > 2)
    flipped = sum(1 for e, n in directed.items() if n > 1)             # same direction twice = inconsistent winding
    unit = 1000.0 if max(hi[k] - lo[k] for k in range(3)) < 2 else 1.0   # metres -> mm
    r = {
        "file": os.path.basename(path), "triangles": len(tris),
        "size_mm": [round((hi[k] - lo[k]) * unit, 2) for k in range(3)],
        "volume_cm3": round(abs(vol) * unit ** 3 / 1000, 2), "volume_sign": "+" if vol > 0 else "-",
        "open_edges": open_edges, "nonmanifold_edges": nonmanifold, "inconsistent_edges": flipped,
        "degenerate": degenerate,
    }
    r["ok"] = len(tris) > 0 and open_edges == 0 and nonmanifold == 0 and flipped == 0 and vol > 0
    return r


def main() -> int:
    files = sorted(f for f in os.listdir(OUT) if f.lower().endswith(".stl"))
    res = [check(os.path.join(OUT, f)) for f in files]
    for r in res:
        print(("OK  " if r["ok"] else "FAIL") + f" {r['file']}: {r['triangles']} tri, "
              f"{r['size_mm'][0]} x {r['size_mm'][1]} x {r['size_mm'][2]} mm, {r['volume_cm3']} cm3, "
              f"open {r['open_edges']}, non-manifold {r['nonmanifold_edges']}, winding {r['inconsistent_edges']}, degenerate {r['degenerate']}")
    json.dump(res, open(os.path.join(OUT, "stl_check.json"), "w"), indent=1)
    return 0 if res and all(r["ok"] for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
