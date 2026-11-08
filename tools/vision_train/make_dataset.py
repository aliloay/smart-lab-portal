"""
Asset detector dataset (2026-10-28, owner: "detect the reusable bin across the room, without the QR code").
Hand-drawn boxes (normalised x1, y1, x2, y2) around the WHOLE station - the bin plus its control box - in the owner's
photos. Train = close-ups (backend/data/asset_refs/...); val = the owner's wide room photos, never trained on.
Photos stay local (git-ignored); only this script and the boxes are kept.
    .venv/Scripts/python make_dataset.py <dir with the wide photos>   -> data/assets/{images,labels}/{train,val} + data.yaml
"""
import os
import shutil
import sys

from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
REFS = os.path.join(HERE, "..", "..", "backend", "data", "asset_refs", "SLAB_D_REUSE_BIN_1")
CLASSES = ["reusable_bin"]
TRAIN = {  # reuse_bin_NN.jpg -> box
    1: (0.0, .02, 1.0, .85), 2: (.17, .15, .90, .93), 3: (.02, .15, .93, .76), 4: (.08, .15, 1.0, .70),
    5: (.12, .12, 1.0, .73), 6: (.15, .12, .95, .83), 7: (.20, .25, .97, .84), 8: (.05, .18, .95, .75),
    9: (.10, .20, .85, .92), 10: (0.0, .25, 1.0, .82), 11: (0.0, .25, 1.0, .82), 12: (0.0, 0.0, 1.0, .90),
    13: (0.0, .12, .92, .88), 14: (0.0, 0.0, 1.0, 1.0), 15: (.05, .25, 1.0, .82), 16: (0.0, 0.0, .75, 1.0),
    17: (.10, .12, .95, .80), 18: (0.0, .08, 1.0, .88), 19: (0.0, .12, 1.0, .85), 20: (0.0, .12, .95, .85),
    21: (0.0, 0.0, 1.0, .88), 22: (0.0, .08, 1.0, .88), 23: (0.0, .08, 1.0, .75), 24: (0.0, 0.0, 1.0, .75),
    25: (.10, .20, .95, .92), 26: (.25, .25, .97, .86), 27: (0.0, .22, .95, .86),
}
VAL = {  # owner's wide room photos (file stem) -> box
    "b5eb016d": (.37, .38, .58, .56), "52223cf7": (.46, .33, .81, .60), "05951a86": (.43, .46, .64, .59),
    "8cbf6087": (.50, .50, .68, .60), "71806aa7": (.44, .50, .67, .64), "044426c0": (.38, .48, .53, .57),
    "2704e421": (.29, .43, .55, .63),
}


def put(src, split, name, box, out):
    img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    img.thumbnail((1280, 1280))
    os.makedirs(os.path.join(out, "images", split), exist_ok=True)
    os.makedirs(os.path.join(out, "labels", split), exist_ok=True)
    img.save(os.path.join(out, "images", split, name + ".jpg"), quality=92)
    x1, y1, x2, y2 = box
    with open(os.path.join(out, "labels", split, name + ".txt"), "w") as f:
        f.write(f"0 {(x1 + x2) / 2:.4f} {(y1 + y2) / 2:.4f} {x2 - x1:.4f} {y2 - y1:.4f}\n")


def main():
    wide = sys.argv[1]
    out = os.path.join(HERE, "data", "assets")
    shutil.rmtree(out, ignore_errors=True)
    for n, box in TRAIN.items():
        put(os.path.join(REFS, f"reuse_bin_{n:02d}.jpg"), "train", f"bin_{n:02d}", box, out)
    for stem, box in VAL.items():
        put(os.path.join(wide, stem + ".jpg"), "val", f"wide_{stem}", box, out)
    with open(os.path.join(out, "data.yaml"), "w") as f:
        f.write(f"path: {out}\ntrain: images/train\nval: images/val\nnames:\n" +
                "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)))
    print("train", len(TRAIN), "val", len(VAL), "->", out)


if __name__ == "__main__":
    main()
