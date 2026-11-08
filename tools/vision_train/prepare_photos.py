"""Owner photo drop -> plain JPGs (2026-10-30): iPhone HEIC and videos in a zip folder, ready for the automatic
labeller. iPhone photos are EXIF-rotated to upright, shrunk to 1280 px and saved WITHOUT EXIF (so no GPS leaves this
laptop); videos give 2 frames a second in shooting order (neighbouring frames are near-copies).
    .venv/Scripts/python prepare_photos.py <folder with the drop> <out folder> [fps=2]
"""
import glob
import os
import sys

import cv2
import pillow_heif
from PIL import Image, ImageOps

pillow_heif.register_heif_opener()


def main():
    src, out = sys.argv[1], sys.argv[2]
    fps = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    os.makedirs(out, exist_ok=True)
    n = v = 0
    for p in sorted(glob.glob(os.path.join(src, "**", "*"), recursive=True)):
        if "__MACOSX" in p:
            continue
        low = p.lower()
        if low.endswith((".heic", ".jpg", ".jpeg", ".png")):
            im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
            im.thumbnail((1280, 1280))
            im.save(os.path.join(out, f"{n:04d}.jpg"), quality=90)
            n += 1
        elif low.endswith((".mov", ".mp4", ".m4v", ".avi")):
            c = cv2.VideoCapture(p)
            step = max(1, round((c.get(cv2.CAP_PROP_FPS) or 30) / fps))
            i = 0
            while True:
                ok, f = c.read()
                if not ok:
                    break
                if i % step == 0:
                    im = Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
                    im.thumbnail((1280, 1280))
                    im.save(os.path.join(out, f"{n:04d}.jpg"), quality=90)
                    n += 1
                    v += 1
                i += 1
    print(f"{n} images ({v} of them video frames) -> {out}")


if __name__ == "__main__":
    main()
