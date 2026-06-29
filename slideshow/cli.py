"""CLI entry point: build a chronological photo slideshow as an MP4."""
from __future__ import annotations

import argparse
from pathlib import Path

from .render import DEFAULT_RESOLUTION, build_slideshow
from .scanner import scan_photos


def parse_resolution(value: str) -> tuple[int, int]:
    try:
        w, h = (int(x) for x in value.lower().split("x"))
        return w, h
    except ValueError as exc:
        raise argparse.ArgumentTypeError("resolution must be WIDTHxHEIGHT, e.g. 1920x1080") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a chronological MP4 slideshow from a folder of year-named photo subfolders.",
    )
    parser.add_argument("input_folder", type=Path, help="Root folder containing year subfolders (e.g. 2018, 2019, ...)")
    parser.add_argument("output_file", type=Path, help="Output .mp4 path")
    parser.add_argument(
        "--seconds-per-image", type=float, default=3.0, help="How long each photo is shown, in seconds (default: 3.0)"
    )
    parser.add_argument(
        "--transition-seconds", type=float, default=0.5, help="Crossfade duration between photos, in seconds (default: 0.5)"
    )
    parser.add_argument(
        "--resolution", type=parse_resolution, default=DEFAULT_RESOLUTION, help="Output resolution as WIDTHxHEIGHT (default: 1920x1080)"
    )
    parser.add_argument("--soundtrack", type=Path, default=None, help="Optional audio file to play under the slideshow")
    parser.add_argument(
        "--soundtrack-volume", type=float, default=1.0, help="Soundtrack volume multiplier (default: 1.0)"
    )
    parser.add_argument("--fps", type=int, default=24, help="Output video frame rate (default: 24)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.input_folder.is_dir():
        print(f"Input folder not found: {args.input_folder}")
        return 1
    if args.soundtrack is not None and not args.soundtrack.is_file():
        print(f"Soundtrack file not found: {args.soundtrack}")
        return 1

    photos = scan_photos(args.input_folder)
    if not photos:
        print(f"No photos found under {args.input_folder}")
        return 1

    print(f"Found {len(photos)} photos spanning {photos[0].timestamp.date()} to {photos[-1].timestamp.date()}.")

    total_seconds = len(photos) * args.seconds_per_image - max(len(photos) - 1, 0) * args.transition_seconds
    minutes, seconds = divmod(round(total_seconds), 60)
    print(f"Calculated slideshow length: {minutes}m {seconds}s. Pick a soundtrack close to this length for the best fit.")

    build_slideshow(
        photos=photos,
        output_path=args.output_file,
        seconds_per_image=args.seconds_per_image,
        transition_seconds=args.transition_seconds,
        resolution=args.resolution,
        soundtrack_path=args.soundtrack,
        soundtrack_volume=args.soundtrack_volume,
        fps=args.fps,
    )

    print(f"Slideshow written to {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
