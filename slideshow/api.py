"""FastAPI wrapper around the slideshow builder.

Run with: uvicorn slideshow.api:app --reload
Swagger UI is then available at http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import shutil
import threading
import uuid
from enum import Enum
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .render import DEFAULT_RESOLUTION, build_slideshow
from .scanner import DEFAULT_PHOTOS_DIR, DEFAULT_SOUNDTRACKS_DIR, list_default_soundtracks, scan_photos

app = FastAPI(
    title="Photo Slideshow API",
    description="Generate chronological MP4 slideshows from a folder of photos, ordered by capture date regardless of folder layout.",
    version="0.1.0",
)

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"
_SOUNDTRACK_DIRNAME = DEFAULT_SOUNDTRACKS_DIR.name


def _upload_base_dir(upload_id: Optional[str]) -> tuple[str, Path]:
    """Resolve where an upload should land: a fresh/named batch under
    `uploads/`, or the shared default photos folder when no upload_id is
    given at all."""
    if upload_id is None:
        return "default", DEFAULT_PHOTOS_DIR
    return upload_id, UPLOAD_ROOT / upload_id


class UploadResult(BaseModel):
    upload_id: str
    saved_files: list[str]
    input_folder: Optional[str] = Field(
        default=None, description="Pass this as `input_folder` in POST /slideshows"
    )
    soundtrack_paths: Optional[list[str]] = Field(
        default=None, description="Pass these as `soundtrack` in POST /slideshows"
    )


def _save_uploads(dest_dir: Path, files: list[UploadFile]) -> list[str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for upload in files:
        dest = dest_dir / Path(upload.filename).name
        with dest.open("wb") as out:
            shutil.copyfileobj(upload.file, out)
        saved.append(str(dest))
    return saved


@app.post(
    "/uploads/photos",
    response_model=UploadResult,
    summary="Upload photos for the slideshow",
)
def upload_photos(
    batch_label: str = Form(
        default="batch",
        description=(
            "Just a subfolder name to keep this upload call's files together (e.g. 'phone-backup'). "
            "Purely organizational - photos are sorted by capture date regardless of folder, not by this label."
        ),
    ),
    upload_id: Optional[str] = Form(
        default=None,
        description="Reuse an existing upload_id to add more photos to the same batch. Leave empty to upload into the shared default photos folder.",
    ),
    files: list[UploadFile] = File(..., description="Photo files"),
) -> UploadResult:
    resolved_id, base_dir = _upload_base_dir(upload_id)
    saved = _save_uploads(base_dir / batch_label, files)
    return UploadResult(upload_id=resolved_id, saved_files=saved, input_folder=str(base_dir))


@app.post(
    "/uploads/soundtracks",
    response_model=UploadResult,
    summary="Upload one or more soundtrack audio files",
)
def upload_soundtracks(
    upload_id: Optional[str] = Form(
        default=None,
        description=(
            "Reuse an existing upload_id to keep the soundtrack alongside its photos. "
            "Leave empty to use the shared default photos folder."
        ),
    ),
    files: list[UploadFile] = File(..., description="Audio files, in the order they should play"),
) -> UploadResult:
    resolved_id, base_dir = _upload_base_dir(upload_id)
    saved = _save_uploads(base_dir / _SOUNDTRACK_DIRNAME, files)
    return UploadResult(upload_id=resolved_id, saved_files=saved, soundtrack_paths=saved)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class SlideshowRequest(BaseModel):
    input_folder: Optional[str] = Field(
        default=None,
        description=(
            "Root folder to scan recursively for photos (any subfolder layout - sorted by capture date, not folder structure). "
            f"Defaults to the shared photos folder ({DEFAULT_PHOTOS_DIR}) if omitted."
        ),
    )
    output_file: str = Field(..., description="Destination path for the rendered .mp4")
    seconds_per_image: float = Field(default=3.0, description="How long each photo is shown, in seconds")
    transition_seconds: float = Field(default=0.5, description="Crossfade duration between photos, in seconds")
    resolution_width: int = Field(default=DEFAULT_RESOLUTION[0])
    resolution_height: int = Field(default=DEFAULT_RESOLUTION[1])
    soundtrack: Optional[list[str]] = Field(
        default=None,
        description=(
            "One or more audio file paths, played in order, looped/trimmed to fit. "
            f"Defaults to any audio files found in {DEFAULT_SOUNDTRACKS_DIR} if omitted."
        ),
    )
    soundtrack_volume: float = Field(default=1.0)
    audio_fade_seconds: float = Field(
        default=1.0, description="Fade applied at every track join and at any cut point"
    )
    animation: str = Field(
        default="ken-burns",
        pattern="^(ken-burns|static)$",
        description="'ken-burns' slowly zooms/pans each photo (default), 'static' shows it motionless",
    )
    zoom: float = Field(default=1.15, description="How far the Ken Burns effect zooms in, as a multiplier")
    fps: int = Field(default=24)


class JobInfo(BaseModel):
    job_id: str
    status: JobStatus
    photo_count: Optional[int] = None
    calculated_length_seconds: Optional[float] = None
    output_file: Optional[str] = None
    error: Optional[str] = None


_jobs: dict[str, JobInfo] = {}
_jobs_lock = threading.Lock()


def _run_job(job_id: str, req: SlideshowRequest) -> None:
    try:
        with _jobs_lock:
            _jobs[job_id].status = JobStatus.RUNNING

        photos = scan_photos(Path(req.input_folder))
        if not photos:
            raise ValueError(f"No photos found under {req.input_folder}")

        total_seconds = len(photos) * req.seconds_per_image - max(len(photos) - 1, 0) * req.transition_seconds
        with _jobs_lock:
            _jobs[job_id].photo_count = len(photos)
            _jobs[job_id].calculated_length_seconds = round(total_seconds, 2)

        build_slideshow(
            photos=photos,
            output_path=Path(req.output_file),
            seconds_per_image=req.seconds_per_image,
            transition_seconds=req.transition_seconds,
            resolution=(req.resolution_width, req.resolution_height),
            soundtrack_paths=[Path(p) for p in req.soundtrack] if req.soundtrack else None,
            soundtrack_volume=req.soundtrack_volume,
            audio_fade_seconds=req.audio_fade_seconds,
            animation=req.animation,
            zoom=req.zoom,
            fps=req.fps,
        )

        with _jobs_lock:
            _jobs[job_id].status = JobStatus.DONE
            _jobs[job_id].output_file = req.output_file
    except Exception as exc:  # noqa: BLE001 - surface any failure on the job record
        with _jobs_lock:
            _jobs[job_id].status = JobStatus.ERROR
            _jobs[job_id].error = str(exc)


@app.post("/slideshows", response_model=JobInfo, status_code=202, summary="Start generating a chronological slideshow")
def create_slideshow(req: SlideshowRequest) -> JobInfo:
    req.input_folder = req.input_folder or str(DEFAULT_PHOTOS_DIR)
    if not Path(req.input_folder).is_dir():
        raise HTTPException(status_code=400, detail=f"Input folder not found: {req.input_folder}")
    if req.soundtrack:
        missing = [p for p in req.soundtrack if not Path(p).is_file()]
        if missing:
            raise HTTPException(status_code=400, detail=f"Soundtrack file(s) not found: {', '.join(missing)}")
    else:
        defaults = list_default_soundtracks()
        if defaults:
            req.soundtrack = [str(p) for p in defaults]

    job_id = uuid.uuid4().hex
    job = JobInfo(job_id=job_id, status=JobStatus.PENDING)
    with _jobs_lock:
        _jobs[job_id] = job

    threading.Thread(target=_run_job, args=(job_id, req), daemon=True).start()
    return job


@app.get("/slideshows/{job_id}", response_model=JobInfo, summary="Check slideshow generation status")
def get_slideshow(job_id: str) -> JobInfo:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/slideshows/{job_id}/download", summary="Download the rendered MP4 once status is 'done'")
def download_slideshow(job_id: str) -> FileResponse:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE or not job.output_file:
        raise HTTPException(status_code=409, detail=f"Job is not finished (status: {job.status})")
    return FileResponse(job.output_file, media_type="video/mp4", filename=Path(job.output_file).name)
