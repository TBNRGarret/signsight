"""Decode uploads, remove metadata and keep server-generated paths private."""

import hashlib
import io
import math
import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


@dataclass
class SanitizedImage:
    data: bytes
    width: int
    height: int
    sha256: str
    latitude: float | None
    longitude: float | None


def gps_hint(image):
    try:
        gps = image.getexif().get_ifd(34853)
        def coordinate(value, ref, positive, negative, bound):
            if ref not in (positive, negative) or len(value) != 3:
                return None
            parts = [float(part) for part in value]
            if any(not math.isfinite(part) or part < 0 for part in parts) or parts[1] >= 60 or parts[2] >= 60:
                return None
            result = parts[0] + parts[1] / 60 + parts[2] / 3600
            return result * (-1 if ref == negative else 1) if result <= bound else None
        latitude = coordinate(gps[2], gps[1], "N", "S", 90)
        longitude = coordinate(gps[4], gps[3], "E", "W", 180)
        return (latitude, longitude) if latitude is not None and longitude is not None else (None, None)
    except (KeyError, TypeError, ValueError, AttributeError, ZeroDivisionError, OverflowError, OSError):
        return None, None


def sanitize_image(data: bytes, content_type: str | None, max_pixels: int) -> SanitizedImage:
    if not data:
        raise HTTPException(400, "Image is empty")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in FORMATS:
                raise HTTPException(415, "Only JPEG, PNG and WebP images are supported")
            if content_type not in (None, "application/octet-stream", FORMATS[probe.format]):
                raise HTTPException(415, "Content type does not match the decoded image")
            if probe.width * probe.height > max_pixels:
                raise HTTPException(413, "Image dimensions exceed the pixel limit")
            if getattr(probe, "n_frames", 1) != 1:
                raise HTTPException(415, "Animated images are not supported")
            probe.verify()
        with Image.open(io.BytesIO(data)) as source:
            latitude, longitude = gps_hint(source)
            oriented = ImageOps.exif_transpose(source)
            rgb = oriented.convert("RGB")
            rgb.info.clear()
            output = io.BytesIO()
            rgb.save(output, format="JPEG", quality=90, exif=b"", icc_profile=None)
            result = output.getvalue()
            return SanitizedImage(result, rgb.width, rgb.height, hashlib.sha256(result).hexdigest(), latitude, longitude)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(413, "Image dimensions exceed the pixel limit") from None
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, RuntimeError):
        raise HTTPException(400, "Image cannot be decoded") from None


class ImageStore:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def path(self, key: str):
        if not re.fullmatch(r"[a-f0-9-]{36}\.jpg", key):
            raise HTTPException(404, "Image file not found")
        candidate = (self.root / key).resolve()
        if candidate.parent != self.root:
            raise HTTPException(404, "Image file not found")
        return candidate

    def save(self, key: str, data: bytes):
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path(key)
        target = path.open("xb")  # A collision must never delete an existing image.
        try:
            with target:
                target.write(data)
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def remove(self, key: str):
        self.path(key).unlink(missing_ok=True)

    def read(self, key: str, sha256: str):
        try:
            data = self.path(key).read_bytes()
        except FileNotFoundError:
            raise HTTPException(404, "Image file not found") from None
        if hashlib.sha256(data).hexdigest() != sha256:
            raise HTTPException(503, "Image integrity check failed")
        return data
