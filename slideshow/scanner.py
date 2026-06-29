"""Scan a folder tree for photos and return them in chronological order, regardless of folder layout."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ExifTags

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".heic"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}

# Default root folder to scan when the caller doesn't specify one. Created on
# demand if missing. Subfolders (e.g. by year) are just for the user's own
# organization - scan_photos walks the whole tree and ignores folder names.
DEFAULT_PHOTOS_DIR = Path(__file__).resolve().parent.parent / "photos"

# Default folder for soundtracks, used when no --soundtrack is given.
# Lives inside DEFAULT_PHOTOS_DIR so a single upload batch covers both.
DEFAULT_SOUNDTRACKS_DIR = DEFAULT_PHOTOS_DIR / "_soundtracks"

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


def _photo_timestamp(path: Path) -> dt.datetime:
    exif_dt = _exif_datetime(path)
    if exif_dt is not None:
        return exif_dt
    return dt.datetime.fromtimestamp(path.stat().st_mtime)


def scan_photos(root: Path) -> list[Photo]:
    """Return every photo found anywhere under `root`, sorted chronologically.

    Folder layout is irrelevant - photos are found by walking the whole
    tree and ordered purely by EXIF capture date (falling back to file
    modification time), not by which subfolder they happen to live in.
    """
    photos: list[Photo] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if any(part.startswith("_") for part in path.relative_to(root).parent.parts):
            continue
        photos.append(Photo(path=path, timestamp=_photo_timestamp(path)))

    photos.sort(key=lambda p: (p.timestamp, str(p.path)))
    return photos


def list_default_soundtracks(folder: Path = DEFAULT_SOUNDTRACKS_DIR) -> list[Path]:
    """Return audio files in `folder`, sorted by name, for use when no
    --soundtrack is explicitly given."""
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)
