# photo-slideshow

Turn a folder of photos into a single video slideshow — no PowerPoint slowdowns or crashes, just point it at your photos and get an MP4 back.

Don't worry about organizing your photos first. Drop them into any folder structure you like (by year, by event, or just dumped in one place) — they'll automatically be put in the right order by when they were taken.

## Quick start

```
uv sync
```

You'll also need [ffmpeg](https://ffmpeg.org/download.html) installed and on your PATH.

Then generate a slideshow:

```
uv run python -m slideshow.cli "C:\Photos" "C:\Output\slideshow.mp4"
```

No photos folder handy? Just give it an output path and drop your pictures into the bundled `photos/` folder:

```
uv run python -m slideshow.cli "C:\Output\slideshow.mp4"
```

Want music behind it? Add a soundtrack:

```
uv run python -m slideshow.cli "C:\Photos" "C:\Output\slideshow.mp4" --soundtrack "C:\Music\song1.mp3"
```

Or drop audio files into `photos/_soundtracks/` and they'll be picked up automatically.

## Common options

- `--seconds-per-image` — how long each photo stays on screen (default 3 seconds)
- `--soundtrack` — background music; supports multiple files, looped/trimmed to fit
- `--animation` — `ken-burns` (default) gently zooms/pans each photo; use `static` for no motion
- `--resolution` — output video resolution (default `1920x1080`)
- `--fps` — output frame rate (default 24)

See the [technical docs](docs/TECHNICAL.md) for the full option list, the REST API, and how everything works under the hood.

## Also available: a web API

If you'd rather integrate this into another app instead of using the command line, a REST API with interactive Swagger docs is included:

```
uv run uvicorn slideshow.api:app --reload
```

Then open http://127.0.0.1:8000/docs in your browser.
