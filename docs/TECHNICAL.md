# Technical documentation

CLI that turns a folder of photos into a single chronological MP4 slideshow. Renders straight to video via moviepy/ffmpeg instead of relying on PowerPoint, which slows down or crashes with large photo counts.

## Architecture

```
                +----------------+
                |  slideshow.cli |  (argparse entry point)
                +----------------+
                         |
                         v
                +----------------+        +-----------------+
                | slideshow.api  |------->| slideshow.render |
                | (FastAPI/REST) |        | (moviepy/ffmpeg) |
                +----------------+        +-----------------+
                         |                         ^
                         v                         |
                +----------------+                 |
                | slideshow.     |-----------------+
                | scanner        |
                | (EXIF date     |
                |  ordering)     |
                +----------------+
```

Both the CLI and the REST API call into the same `scanner` (orders photos) and `render` (builds the video) modules — the API just adds upload handling and background job tracking on top.

## Photo ordering

Folder layout doesn't matter — the whole tree is scanned recursively and every photo found is ordered by EXIF capture date (falling back to file modification time), regardless of which subfolder it's in:

```
Photos/
  img1.jpg
  vacation-2019/
    img2.jpg
    img3.jpg
  2018/
    sub-folder/
      img4.jpg
```

## CLI usage

```
python -m slideshow.cli "C:\Photos" "C:\Output\slideshow.mp4" --seconds-per-image 3 --soundtrack "C:\Music\song1.mp3" "C:\Music\song2.mp3"
```

`input_folder` is optional — omit it and pass only the output path:

```
python -m slideshow.cli "C:\Output\slideshow.mp4"
```

to use the bundled `photos/` folder at the project root as the default. If that folder is empty, the CLI creates it and tells you to add photos before rerunning. The same default applies to the REST API's `input_folder` field and to the upload endpoints when no `upload_id` is given.

The console first prints the calculated slideshow length (from photo count and `--seconds-per-image`) so you know how long a soundtrack to pick.

### Options

- `--seconds-per-image` — how long each photo is shown (default 3.0)
- `--transition-seconds` — crossfade duration between photos (default 0.5)
- `--resolution` — output resolution, e.g. `1920x1080` (default)
- `--soundtrack` — one or more audio files, played in order, looped or trimmed to match the video length exactly. If omitted, any audio files found in `photos/_soundtracks/` are used automatically (sorted by filename)
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

- `POST /uploads/photos` — multipart upload (`files`, plus an optional `batch_label` just to keep each call's files in their own subfolder). Photos are still ordered by capture date regardless of this label. Pass back the same `upload_id` across calls to group them into one batch. Returns `input_folder` to use next.
- `POST /uploads/soundtracks` — multipart upload of one or more audio files for the same `upload_id`. Returns `soundtrack_paths` to use next.
- `POST /slideshows` — body matches the CLI options (`input_folder`, `output_file`, `seconds_per_image`, `soundtrack`, etc.); returns `202` with a `job_id` immediately. `input_folder`/`soundtrack` can be either paths already on the server, or the values returned by the upload endpoints above.
- `GET /slideshows/{job_id}` — poll for `status` (`pending` / `running` / `done` / `error`), `photo_count`, and `calculated_length_seconds`.
- `GET /slideshows/{job_id}/download` — streams the finished `.mp4` once `status` is `done`.

Uploaded files are written under `uploads/<upload_id>/<batch_label>/...` next to the project (gitignored), or directly into `photos/`/`photos/_soundtracks/` when no `upload_id` is given. `output_file` in `POST /slideshows` is still a path on the server — point it somewhere writable, e.g. `uploads/<upload_id>/out.mp4`, then download it via the job's download endpoint.
