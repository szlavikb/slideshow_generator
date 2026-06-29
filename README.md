# photo-slideshow

CLI that turns a folder of year-named photo subfolders (e.g. `2018/`, `2019/`, `2020/`)
into a single chronological MP4 slideshow. Avoids PowerPoint's slowdown/crash issues
with large photo counts by rendering straight to video.

Photos are ordered using EXIF capture date when available, falling back to file
modification time (corrected to the containing year folder).

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

You also need [ffmpeg](https://ffmpeg.org/download.html) on your PATH (moviepy shells out to it).

## Usage

```
python -m slideshow.cli "C:\Photos" "C:\Output\slideshow.mp4" --seconds-per-image 3 --soundtrack "C:\Music\song1.mp3" "C:\Music\song2.mp3"
```

The console first prints the calculated slideshow length (from photo count and `--seconds-per-image`) so you know how long a soundtrack to pick.

### Options

- `--seconds-per-image` — how long each photo is shown (default 3.0)
- `--transition-seconds` — crossfade duration between photos (default 0.5)
- `--resolution` — output resolution, e.g. `1920x1080` (default)
- `--soundtrack` — one or more audio files, played in order, looped or trimmed to match the video length exactly
- `--soundtrack-volume` — volume multiplier for the soundtrack (default 1.0)
- `--audio-fade-seconds` — fade applied at every track join and at any cut point, so looping/trimming/concatenating never clicks or jumps abruptly (default 1.0)
- `--animation` — `ken-burns` (default) slowly zooms/pans each photo instead of showing it motionless; `static` disables this
- `--zoom` — how far the Ken Burns effect zooms in, as a multiplier (default 1.15)
- `--fps` — output frame rate (default 24)

## REST API (Swagger)

A FastAPI wrapper exposes the same functionality over HTTP, with interactive Swagger docs.

```
uvicorn slideshow.api:app --reload
```

Then open http://127.0.0.1:8000/docs for the Swagger UI, or http://127.0.0.1:8000/redoc for ReDoc.

Rendering happens in a background thread per job, since a slideshow can take a while to encode:

- `POST /slideshows` — body matches the CLI options (`input_folder`, `output_file`, `seconds_per_image`, `soundtrack`, etc.); returns `202` with a `job_id` immediately.
- `GET /slideshows/{job_id}` — poll for `status` (`pending` / `running` / `done` / `error`), `photo_count`, and `calculated_length_seconds`.
- `GET /slideshows/{job_id}/download` — streams the finished `.mp4` once `status` is `done`.

All paths (`input_folder`, `output_file`, `soundtrack`) refer to locations on the machine running the API, not uploaded files.

## Expected folder layout

```
Photos/
  2018/
    img1.jpg
    img2.jpg
  2019/
    img3.jpg
  2020/
    sub-folder/
      img4.jpg
```
