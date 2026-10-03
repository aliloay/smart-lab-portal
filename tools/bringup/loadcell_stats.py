"""
Load-cell statistics from a serial_log.py CSV - only from rows you logged.

    py loadcell_stats.py accuracy logs/2026-10-04_..._known-masses.csv
    py loadcell_stats.py noise    logs/2026-10-04_..._noise.csv
    py loadcell_stats.py drift    logs/2026-10-04_..._drift.csv

accuracy  each "avg" row is paired with the latest "# ref <grams>" note
          before it (the reference mass on the platform, from the reference
          scale). Per reference: repeats, mean reading, bias (mean - ref),
          absolute and percentage error, repeatability (sample standard
          deviation of the repeated means, needs >= 2 repeats).
noise     "lc" rows (stream mode): number of samples, mean, standard
          deviation, peak-to-peak, sample rate - in grams when calibrated,
          else raw counts. --from / --to (node ms) cut a window.
drift     "lc" rows, else "mass" rows: least-squares slope in g per hour
          and the difference between the first and last 10 % of samples.

Nothing is estimated beyond these formulas; with too few rows the script
says so instead of printing a number.
"""
from __future__ import annotations

import argparse
import math
import statistics as st
import sys


def rows(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split(",")
            if len(parts) >= 3:
                yield parts[2], parts[3:]


def fnum(s):
    try:
        v = float(s)
        return None if math.isnan(v) else v
    except ValueError:
        return None


def accuracy(path):
    ref, pairs = None, []
    for kind, f in rows(path):
        if kind == "NOTE" and f and f[0].lower().startswith("ref "):
            ref = fnum(f[0].split()[1])
        elif kind == "avg" and len(f) >= 6:
            g = fnum(f[4])
            if ref is None or g is None:
                continue
            pairs.append((ref, g, fnum(f[5]), int(f[1])))
    if not pairs:
        sys.exit('No "avg" rows after a "# ref <grams>" note (or the cell is not calibrated).')
    print(f"{len(pairs)} avg rows paired with a reference note\n")
    print("| ref (g) | repeats | mean reading (g) | bias (g) | abs error (g) | error (%) | repeatability sd (g) | within-sample sd (g) |")
    print("|---|---|---|---|---|---|---|---|")
    worst = 0.0
    for r in sorted({p[0] for p in pairs}):
        g = [p[1] for p in pairs if p[0] == r]
        sd_in = [p[2] for p in pairs if p[0] == r and p[2] is not None]
        m = st.mean(g)
        bias = m - r
        pct = f"{abs(bias) / r * 100:.2f}" if r > 0 else "n/a (zero ref)"
        rep = f"{st.stdev(g):.3f}" if len(g) >= 2 else "needs >= 2"
        within = f"{st.mean(sd_in):.3f}" if sd_in else "-"
        worst = max(worst, abs(bias))
        print(f"| {r:g} | {len(g)} | {m:.3f} | {bias:+.3f} | {abs(bias):.3f} | {pct} | {rep} | {within} |")
    print(f"\nLargest absolute error: {worst:.3f} g")


def lc_series(path, a=None, b=None):
    out = []
    for kind, f in rows(path):
        if kind == "lc" and len(f) >= 3:
            t = int(f[0])
            if (a is not None and t < a) or (b is not None and t > b):
                continue
            g = fnum(f[2])
            out.append((t, g if g is not None else float(f[1]), g is not None))
    return out


def noise(path, a, b):
    s = lc_series(path, a, b)
    if len(s) < 10:
        sys.exit(f'Only {len(s)} "lc" rows - stream for longer (type "stream" on the node).')
    v = [x[1] for x in s]
    unit = "g" if s[0][2] else "raw counts"
    dur = (s[-1][0] - s[0][0]) / 1000
    print(f"{len(v)} samples over {dur:.1f} s ({len(v) / dur:.2f} samples/s), unit: {unit}")
    print(f"mean {st.mean(v):.4f}, sd {st.stdev(v):.4f}, peak-to-peak {max(v) - min(v):.4f}")


def drift(path):
    s = [(t, g) for t, g, _ in lc_series(path)]
    unit = "g"
    if len(s) < 20:
        s = [(int(f[0]), fnum(f[1])) for k, f in rows(path) if k == "mass" and len(f) >= 2 and fnum(f[1]) is not None]
    if len(s) < 20:
        sys.exit("Fewer than 20 samples - log for longer.")
    t0 = s[0][0]
    x = [(t - t0) / 3.6e6 for t, _ in s]          # hours
    y = [g for _, g in s]
    mx, my = st.mean(x), st.mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    slope = sum((a - mx) * (b - my) for a, b in zip(x, y)) / sxx if sxx else float("nan")
    k = max(1, len(y) // 10)
    print(f"{len(y)} samples over {x[-1] * 60:.1f} min")
    print(f"least-squares slope: {slope:+.4f} {unit}/hour")
    print(f"first 10 % mean {st.mean(y[:k]):.4f}, last 10 % mean {st.mean(y[-k:]):.4f}, "
          f"difference {st.mean(y[-k:]) - st.mean(y[:k]):+.4f} {unit}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["accuracy", "noise", "drift"])
    ap.add_argument("csv")
    ap.add_argument("--from", dest="a", type=int, help="node ms (noise window start)")
    ap.add_argument("--to", dest="b", type=int, help="node ms (noise window end)")
    args = ap.parse_args()
    {"accuracy": lambda: accuracy(args.csv), "noise": lambda: noise(args.csv, args.a, args.b),
     "drift": lambda: drift(args.csv)}[args.what]()


if __name__ == "__main__":
    main()
