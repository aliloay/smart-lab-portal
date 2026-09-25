"""
Turn user photos into the ACCESS GRANTED background on the master's LCD.

    py firmware/tools/make_lcd_photo.py USER1=C:/path/to/ali.jpg
    py firmware/tools/make_lcd_photo.py USER1=ali.jpg USER2=ramy.png

Names are the INTERNAL ids (USER1 / USER2), the same ones the face server
and authorizedUsers[] use. Every run rewrites the header with exactly the
users given, so pass all of them each time.

Writes:
    firmware/SmartLab_Master_Portal/user_photos.h   (compiled into the master)
    firmware/SmartLab_Master_Portal/user_photos_preview.png

Both are gitignored: they are pictures of people. Re-upload the master
sketch after running this.

Needs only OpenCV + numpy - the same Python the face server runs on.
"""
import os
import sys

import cv2
import numpy as np

W, H = 160, 128                  # ST7735 in rotation 3
TOP_BAND = 22                    # darkened for "ACCESS GRANTED"
BOTTOM_BAND = 88                 # darkened from here down for name + hint
BAND_DARKEN = 0.35               # keep 35% of the brightness under text

HERE = os.path.dirname(os.path.abspath(__file__))
SKETCH = os.path.join(HERE, "..", "SmartLab_Master_Portal")

_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def real_format(data):
    """What the file actually is, whatever its extension says."""
    head = data[:32]
    if head[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WEBP"
    if head[4:8] == b"ftyp":
        brand = head[8:12].decode("ascii", "replace")
        return "AVIF" if brand.startswith("avi") else f"HEIC ({brand})"
    return "unknown"


def load(path):
    if not os.path.isfile(path):
        sys.exit(f"no such file: {os.path.abspath(path)}")
    # np.fromfile + imdecode instead of imread: imread cannot open paths with
    # non-ASCII characters on Windows.
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        img = _load_with_pillow(path)
    if img is None:
        fmt = real_format(data.tobytes())
        sys.exit(
            f"cannot decode {path}\n"
            f"The file is actually {fmt}, whatever its name says.\n"
            "Fix: open it in Paint, choose File > Save as > JPEG picture,\n"
            "and run this again with the new file.")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:                       # transparent PNG -> on white
        alpha = img[:, :, 3:4].astype(np.float32) / 255
        img = (img[:, :, :3] * alpha + 255 * (1 - alpha)).astype(np.uint8)
    return img


def _load_with_pillow(path):
    """Fallback for formats OpenCV lacks (HEIC/AVIF need pillow-heif)."""
    try:
        from PIL import Image
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        with Image.open(path) as im:
            return cv2.cvtColor(np.array(im.convert("RGB")), cv2.COLOR_RGB2BGR)
    except Exception:
        return None


def crop_around_face(img):
    """160:128 crop with the face between the two text bands."""
    ih, iw = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = _cascade.detectMultiScale(gray, 1.1, 5,
                                      minSize=(iw // 12, iw // 12))
    if len(faces):
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        cx, cy = x + w / 2, y + h / 2
        ch = h * 2.3                            # face ~43% of the height
        print(f"  face found at {x},{y} size {w}x{h}")
    else:
        cx, cy, ch = iw / 2, ih * 0.45, min(ih, iw / (W / H))
        print("  no face found - using a centred crop")
    cw = ch * W / H
    # Face centre at 45% of the height: below the top band, above the bottom.
    x0, y0 = int(round(cx - cw / 2)), int(round(cy - ch * 0.45))
    x1, y1 = x0 + int(round(cw)), y0 + int(round(ch))
    # Pad with the photo's own edge colour where the crop leaves the image.
    pad = max(0, -x0, -y0, x1 - iw, y1 - ih)
    if pad:
        img = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
        x0, y0, x1, y1 = x0 + pad, y0 + pad, x1 + pad, y1 + pad
    return cv2.resize(img[y0:y1, x0:x1], (W, H), interpolation=cv2.INTER_AREA)


def darken_bands(img):
    out = img.astype(np.float32)
    out[:TOP_BAND] *= BAND_DARKEN
    out[BOTTOM_BAND:] *= BAND_DARKEN
    return out.clip(0, 255).astype(np.uint8)


def to_rgb565(img):
    b, g, r = (img[:, :, i].astype(np.uint16) for i in range(3))
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def main(args):
    pairs = []
    for a in args:
        if "=" not in a:
            sys.exit(__doc__)
        name, path = a.split("=", 1)
        pairs.append((name.strip().upper(), path.strip().strip('"')))
    if not pairs:
        sys.exit(__doc__)

    lines = [
        "// GENERATED by firmware/tools/make_lcd_photo.py - do not edit.",
        "// Gitignored: contains photos of people.",
        "#pragma once",
        "#include <string.h>",
        "",
        f"constexpr int16_t USER_PHOTO_W = {W}, USER_PHOTO_H = {H};",
        "",
    ]
    previews = []
    for name, path in pairs:
        print(f"{name}: {path}")
        img = darken_bands(crop_around_face(load(path)))
        previews.append(img)
        px = to_rgb565(img).flatten()
        lines.append(f"static const uint16_t PHOTO_{name}[{W * H}] PROGMEM = {{")
        for i in range(0, len(px), 16):
            lines.append("  " + ", ".join(f"0x{v:04X}" for v in px[i:i + 16]) + ",")
        lines.append("};")
        lines.append("")

    lines.append("inline const uint16_t *userPhoto(const char *name) {")
    for name, _ in pairs:
        lines.append(f'  if (strcmp(name, "{name}") == 0) return PHOTO_{name};')
    lines.append("  return nullptr;")
    lines.append("}")

    header = os.path.normpath(os.path.join(SKETCH, "user_photos.h"))
    with open(header, "w") as f:
        f.write("\n".join(lines) + "\n")
    preview = os.path.normpath(os.path.join(SKETCH, "user_photos_preview.png"))
    cv2.imwrite(preview, cv2.resize(np.hstack(previews), None, fx=3, fy=3,
                                    interpolation=cv2.INTER_NEAREST))
    print(f"\nwrote {header}")
    print(f"preview (3x): {preview}")
    print("Now re-upload SmartLab_Master_Portal.ino.")


if __name__ == "__main__":
    main(sys.argv[1:])
