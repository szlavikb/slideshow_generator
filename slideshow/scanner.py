"""Scan a root folder of year subfolders and return photos in chronological order."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ExifTags

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".heic"}

# Default root folder for year subfolders (e.g. photos/2018, photos/2019, ...)
# when the caller doesn't specify one. Created on demand if missing.
DEFAULT_PHOTOS_DIR = Path(__file__).resolve().parent.parent / "photos"

_EXIF_DATE_TAG = next(
    (tag for tag, name in ExifTags.TAGS.items() if name == "DateTimeOriginal"), None
)


@dataclass
class Photo:
    path: Path
    timestamp: dt.datetime


def _exif_datetime(path: Path) -> dt.datetime | None:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif or _EXIF_DATE_TAG not in exif:
                return None
            return dt.datetime.strptime(exif[_EXIF_DATE_TAG], "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def _photo_timestamp(path: Path, year_hint: int) -> dt.datetime:
    exif_dt = _exif_datetime(path)
    if exif_dt is not None:
        return exif_dt
    mtime = dt.datetime.fromtimestamp(path.stat().st_mtime)
    if mtime.year != year_hint:
        mtime = mtime.replace(year=year_hint)
    return mtime


def scan_photos(root: Path) -> list[Photo]:
    """Return all photos under root/<year>/ folders, sorted chronologically."""
    photos: list[Photo] = []
    for year_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        try:
            year_hint = int(year_dir.name)
        except ValueError:
            year_hint = dt.datetime.now().year

        for path in sorted(year_dir.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                photos.append(Photo(path=path, timestamp=_photo_timestamp(path, year_hint)))

    photos.sort(key=lambda p: (p.timestamp, str(p.path)))
    return photos
