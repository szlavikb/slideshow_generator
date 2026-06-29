"""Render a chronological list of photos into an MP4 slideshow."""
from __future__ import annotations

from pathlib import Path

from moviepy.editor import (
    AudioFileClip,
    ImageClip,
    afx,
    concatenate_audioclips,
    concatenate_videoclips,
)

from .scanner import Photo

DEFAULT_RESOLUTION = (1920, 1080)


def _fit_clip(clip: ImageClip, resolution: tuple[int, int]) -> ImageClip:
    """Letterbox the image to fill `resolution` without cropping or distortion."""
    target_w, target_h = resolution
    clip = clip.resize(height=target_h) if clip.w / clip.h > target_w / target_h else clip.resize(width=target_w)
    return clip.on_color(size=resolution, color=(0, 0, 0), pos="center")


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
    fps: int = 24,
) -> None:
    if not photos:
        raise ValueError("No photos to render.")

    clips = []
    for photo in photos:
        clip = ImageClip(str(photo.path)).set_duration(seconds_per_image)
        clip = _fit_clip(clip, resolution)
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
