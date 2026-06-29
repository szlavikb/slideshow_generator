"""Render a chronological list of photos into an MP4 slideshow."""
from __future__ import annotations

import random
from pathlib import Path

from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    afx,
    concatenate_audioclips,
    concatenate_videoclips,
)

from .scanner import Photo

DEFAULT_RESOLUTION = (1920, 1080)

# Diagonal pan directions, expressed as the (x, y) offset of the top-left
# corner of an oversized image relative to the canvas, at t=0 and t=duration.
# Panning reveals a different part of the image each time so consecutive
# photos don't all move the same way.
_PAN_DIRECTIONS = [
    ((0, 0), "br"),
    ((1, 1), "tl"),
    ((1, 0), "bl"),
    ((0, 1), "tr"),
]


def _cover_resize(clip: ImageClip, resolution: tuple[int, int], zoom: float = 1.0) -> ImageClip:
    """Resize so the image fully covers `resolution` (cropping overflow), then
    enlarge by `zoom` to leave margin for panning."""
    target_w, target_h = resolution[0] * zoom, resolution[1] * zoom
    return clip.resize(height=target_h) if clip.w / clip.h > target_w / target_h else clip.resize(width=target_w)


def _fit_clip(clip: ImageClip, resolution: tuple[int, int]) -> ImageClip:
    """Letterbox the image to fill `resolution` without cropping or distortion."""
    target_w, target_h = resolution
    clip = clip.resize(height=target_h) if clip.w / clip.h > target_w / target_h else clip.resize(width=target_w)
    return clip.on_color(size=resolution, color=(0, 0, 0), pos="center")


def _ken_burns_clip(
    photo: Photo,
    duration: float,
    resolution: tuple[int, int],
    zoom: float = 1.15,
    rng: random.Random | None = None,
) -> ImageClip:
    """Build a slowly panning/zooming clip (the classic "Ken Burns" effect)
    instead of a static, motionless photo."""
    rng = rng or random
    covered = _cover_resize(ImageClip(str(photo.path)).set_duration(duration), resolution, zoom)

    margin_x = max(covered.w - resolution[0], 0)
    margin_y = max(covered.h - resolution[1], 0)
    (start_frac, _label) = rng.choice(_PAN_DIRECTIONS)
    start_x, start_y = -margin_x * start_frac[0], -margin_y * start_frac[1]
    end_x, end_y = -margin_x * (1 - start_frac[0]), -margin_y * (1 - start_frac[1])

    def position(t: float) -> tuple[float, float]:
        progress = min(t / duration, 1.0) if duration > 0 else 1.0
        return (start_x + (end_x - start_x) * progress, start_y + (end_y - start_y) * progress)

    covered = covered.set_position(position)
    return CompositeVideoClip([covered], size=resolution).set_duration(duration)


def _build_audio_track(
    paths: list[Path],
    target_duration: float,
    volume: float,
    fade_seconds: float = 1.0,
) -> AudioFileClip:
    """Concatenate one or more soundtracks to exactly fill `target_duration`.

    Fades are applied at every join and at any point a track gets cut so
    concatenation/looping/trimming never produces an audible click or an
    abrupt jump.
    """
    clips = []
    for path in paths:
        clip = AudioFileClip(str(path)).fx(afx.volumex, volume)
        fade = min(fade_seconds, clip.duration / 2)
        if fade > 0:
            clip = clip.fx(afx.audio_fadein, fade).fx(afx.audio_fadeout, fade)
        clips.append(clip)

    playlist = concatenate_audioclips(clips) if len(clips) > 1 else clips[0]

    if playlist.duration < target_duration:
        track = playlist.fx(afx.audio_loop, duration=target_duration)
    else:
        track = playlist.subclip(0, target_duration)

    tail_fade = min(fade_seconds, target_duration / 2)
    if tail_fade > 0:
        track = track.fx(afx.audio_fadeout, tail_fade)
    return track


def build_slideshow(
    photos: list[Photo],
    output_path: Path,
    seconds_per_image: float = 3.0,
    transition_seconds: float = 0.5,
    resolution: tuple[int, int] = DEFAULT_RESOLUTION,
    soundtrack_paths: list[Path] | None = None,
    soundtrack_volume: float = 1.0,
    audio_fade_seconds: float = 1.0,
    animation: str = "ken-burns",
    zoom: float = 1.15,
    fps: int = 24,
) -> None:
    if not photos:
        raise ValueError("No photos to render.")

    rng = random.Random(0)
    clips = []
    for photo in photos:
        if animation == "ken-burns":
            clip = _ken_burns_clip(photo, seconds_per_image, resolution, zoom, rng)
        else:
            clip = _fit_clip(ImageClip(str(photo.path)).set_duration(seconds_per_image), resolution)
        if transition_seconds > 0:
            clip = clip.crossfadein(transition_seconds)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose", padding=-transition_seconds if transition_seconds else 0)

    if soundtrack_paths:
        audio = _build_audio_track(soundtrack_paths, video.duration, soundtrack_volume, audio_fade_seconds)
        video = video.set_audio(audio)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac" if soundtrack_paths else None,
        threads=4,
        preset="medium",
    )

    for clip in clips:
        clip.close()
    video.close()
