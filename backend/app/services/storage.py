"""
Object storage for uploaded files, plus image validation and processing.

The issue system only ever talks to the `Storage` interface with opaque keys
such as "issues/42/3f9c...e1.jpg". The first deployment stores them on the
local filesystem; an S3 or MinIO implementation of the same three methods can
replace LocalStorage without the issue code, the database rows or the API
changing at all.
"""
from __future__ import annotations

import io
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings

# Pillow format -> (content type, file extension)
ALLOWED_FORMATS: dict[str, tuple[str, str]] = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}

# Decompression-bomb guard: refuse anything that would decode to more than
# this many pixels, whatever its file size.
MAX_PIXELS = 50_000_000


class Storage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def open(self, key: str) -> Iterator[bytes]: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...


class LocalStorage:
    name = "local-filesystem"

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        # Keys are generated server-side, but resolve and check anyway: a key
        # must never be able to address a file outside the storage root.
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("storage key escapes the storage root")
        return p

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, p)           # atomic: never a half-written image

    def open(self, key: str) -> Iterator[bytes]:
        with self._path(key).open("rb") as fh:
            while chunk := fh.read(64 * 1024):
                yield chunk

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = LocalStorage(settings.UPLOAD_DIR)
    return _storage


def set_storage(storage: Storage) -> None:
    """Swap the backend (tests use a temporary directory)."""
    global _storage
    _storage = storage


# ---------------------------------------------------------------------------
# Image processing
# ---------------------------------------------------------------------------
class ImageRejected(ValueError):
    pass


@dataclass
class ProcessedImage:
    data: bytes
    thumb: bytes
    content_type: str
    ext: str
    width: int
    height: int


def process_image(raw: bytes) -> ProcessedImage:
    """
    Validate an upload by decoding it, then normalise it.

    The file extension and the browser's declared content type are ignored:
    the only thing trusted is what Pillow actually decodes. The image is then
    rotated upright from its EXIF orientation, re-encoded - which drops every
    EXIF field, including the GPS position a phone embeds - and scaled down if
    larger than IMAGE_MAX_DIMENSION. A separate small thumbnail is produced
    for lists and galleries.
    """
    limit = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(raw) == 0:
        raise ImageRejected("The file is empty.")
    if len(raw) > limit:
        raise ImageRejected(f"The file is larger than {settings.MAX_UPLOAD_MB} MB.")

    try:
        probe = Image.open(io.BytesIO(raw))
        fmt = probe.format
        if fmt not in ALLOWED_FORMATS:
            raise ImageRejected("Only JPEG, PNG and WebP images are accepted.")
        if probe.width * probe.height > MAX_PIXELS:
            raise ImageRejected("The image dimensions are too large.")
        probe.verify()                       # structural check, no decode
        img = Image.open(io.BytesIO(raw))    # verify() invalidates; reopen
        img.load()
    except ImageRejected:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError):
        raise ImageRejected("The file is not a valid image.")

    img = ImageOps.exif_transpose(img)
    content_type, ext = ALLOWED_FORMATS[fmt]

    big = settings.IMAGE_MAX_DIMENSION
    if max(img.size) > big:
        img.thumbnail((big, big), Image.Resampling.LANCZOS)

    data = _encode(img, fmt)
    thumb_img = img.copy()
    t = settings.THUMBNAIL_DIMENSION
    thumb_img.thumbnail((t, t), Image.Resampling.LANCZOS)
    thumb = _encode(thumb_img, fmt)
    return ProcessedImage(data=data, thumb=thumb, content_type=content_type,
                          ext=ext, width=img.width, height=img.height)


def _encode(img: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    if fmt == "JPEG":
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.save(buf, "JPEG", quality=88, optimize=True, progressive=True)
    elif fmt == "WEBP":
        img.save(buf, "WEBP", quality=86, method=4)
    else:
        img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def new_key(prefix: str, ext: str) -> tuple[str, str]:
    token = secrets.token_hex(12)
    return f"{prefix}/{token}.{ext}", f"{prefix}/{token}_thumb.{ext}"
