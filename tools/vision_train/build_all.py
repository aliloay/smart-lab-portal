"""
One detector for every object the owner photographed (2026-10-30): the reusable bin, the TP-Link switch and the router in
ONE model, so a single pass answers "which of our things is in this frame" instead of one model per object.

Sources: data/bin_r5 (reusable_bin), data/switch_r1 (network_switch), data/router_r1 (network_router) - each keeps its
own held-out test scenes, so the test split is still never-seen photos. A photo that appears in two sources keeps both
boxes (matched by file hash, never the file name). No-object pictures: the lab-camera frames from before the objects
existed (237) and public COCO photos (450) in train, 80 of them moved to val; the test negatives are the held-out
lab_neg_test (221) + coco_val/negtest (200) and are checked against train by hash.
    .venv/Scripts/python.exe build_all.py [out=data/all_r1]
"""
import hashlib
import json
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
CLASSES = ["reusable_bin", "network_switch", "network_router"]
# (round dir, class id, tag, forced split) - forced split is used when a source's own split is not trusted
SRC = [("bin_r5", 0, "bin", None), ("switch_r1", 1, "sw", None), ("router_r1", 2, "rt", None),
       # 2026-10-30: 59 frames of the owner's 4K lab-bin video (never used before). Automatic boxes there are
       # inconsistent (control box vs whole station), so they only ever go to train, never to the scored test split.
       ("bin_v2", 0, "bin2", "train")]
ORDER = {"train": 0, "val": 1, "test": 2}          # an image keeps the most held-out split it appears in


def digest(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(D, "all_r1")
    shutil.rmtree(out, ignore_errors=True)
    for sp in ORDER:
        os.makedirs(os.path.join(out, "images", sp))
        os.makedirs(os.path.join(out, "labels", sp))
    merged = {}                                    # hash -> {"split", "path", "boxes": [(cls, x1, y1, x2, y2)]}
    for round_dir, cls, _tag, forced in SRC:
        for sp in ORDER:
            for p in sorted(os.path.join(D, round_dir, "images", sp, f) for f in
                            os.listdir(os.path.join(D, round_dir, "images", sp)) if f.lower().endswith(".jpg")):
                lab = p.replace(os.sep + "images" + os.sep, os.sep + "labels" + os.sep)[:-4] + ".txt"
                if not os.path.isfile(lab):
                    continue                       # unlabelled = one of that round's negatives, not used as a positive
                boxes = []
                for line in open(lab):
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    cx, cy, w, h = map(float, parts[1:5])
                    boxes.append((cls, round(cx - w / 2, 5), round(cy - h / 2, 5), round(cx + w / 2, 5), round(cy + h / 2, 5)))
                k = digest(p)
                sp = forced or sp
                if k not in merged:
                    merged[k] = {"split": sp, "path": p, "boxes": boxes}
                else:
                    if ORDER[sp] > ORDER[merged[k]["split"]]:
                        merged[k]["split"] = sp
                    for b in boxes:
                        if b not in merged[k]["boxes"]:
                            merged[k]["boxes"].append(b)
    counts = {sp: 0 for sp in ORDER}
    per_class = {c: {sp: 0 for sp in ORDER} for c in CLASSES}
    for k, m in merged.items():
        sp = m["split"]
        name = k[:12]
        shutil.copy(m["path"], os.path.join(out, "images", sp, name + ".jpg"))
        with open(os.path.join(out, "labels", sp, name + ".txt"), "w") as f:
            for cls, x1, y1, x2, y2 in m["boxes"]:
                f.write(f"{cls} {(x1 + x2) / 2:.5f} {(y1 + y2) / 2:.5f} {x2 - x1:.5f} {y2 - y1:.5f}\n")
                per_class[CLASSES[cls]][sp] += 1
        counts[sp] += 1
    neg_dir = os.path.join(D, "bin_r5", "images", "train")
    negs = sorted(os.path.join(neg_dir, f) for f in os.listdir(neg_dir)
                  if f.startswith(("lab_", "cocov_", "coco_")) and f.lower().endswith(".jpg"))
    # 2026-10-30: 202 frames of the real lab camera (Oct 12, before the bin existed; the switch is out of that view and
    # YOLO-World's "router"/"bin" boxes there were on the green blocks, i.e. junk). They teach the model that the lab's
    # clutter is none of our three objects - the false-alarm side that matters on the phone.
    lab3 = os.path.join(D, "lab3_raw")
    if os.path.isdir(lab3):
        negs += sorted(os.path.join(lab3, f) for f in os.listdir(lab3) if f.lower().endswith(".jpg"))
    random.Random(0).shuffle(negs)
    val_negs, train_negs = negs[:80], negs[80:]
    for sp, pool in (("train", train_negs), ("val", val_negs)):
        for p in pool:
            shutil.copy(p, os.path.join(out, "images", sp, "neg_" + digest(p)[:12] + ".jpg"))
            counts[sp] += 1
    seen = {k[:12] for k in merged}
    held = ([p for p in sorted(os.listdir(os.path.join(D, "lab_neg_test")))]
            + [p for p in sorted(os.listdir(os.path.join(D, "coco_val", "negtest")))])
    for name in held:
        p = os.path.join(D, "lab_neg_test", name) if os.path.exists(os.path.join(D, "lab_neg_test", name)) \
            else os.path.join(D, "coco_val", "negtest", name)
        h = digest(p)[:12]
        if h in seen:
            continue
        seen.add(h)
        shutil.copy(p, os.path.join(out, "images", "test", "negtest_" + h + ".jpg"))
        counts["test"] += 1
    with open(os.path.join(out, "data.yaml"), "w") as f:
        f.write(f"path: {os.path.abspath(out)}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n"
                + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)))
    summary = {"classes": CLASSES, "sources": [s[0] for s in SRC], "images": counts, "boxes_per_class": per_class,
               "train_negatives": len(train_negs), "val_negatives": len(val_negs)}
    json.dump(summary, open(os.path.join(out, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
