"""Render a chronological list of photos into an MP4 slideshow."""
from __future__ import annotations

from pathlib import Path

from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    ImageClip,
    afx,
    concatenate_videoclips,
)

from .scanner import Photo

DEFAULT_RESOLUTION = (1920, 1080)


def _fit_clip(clip: ImageClip, resolution: tuple[int, int]) -> ImageClip:
    """Letterbox the image to fill `resolution` without cropping or distortion."""
    target_w, target_h = resolution
    clip = clip.resize(height=target_h) if clip.w / clip.h > target_w / target_h else clip.resize(width=target_w)
    return clip.on_color(size=resolution, color=(0, 0, 0), pos="center")


def build_slideshow(
    photos: list[Photo],
    output_path: Path,
    seconds_per_image: float = 3.0,
    transition_seconds: float = 0.5,
    resolution: tuple[int, int] = DEFAULT_RESOLUTION,
    soundtrack_path: Path | None = None,
    soundtrack_volume: float = 1.0,
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

    if soundtrack_path is not None:
        audio = AudioFileClip(str(soundtrack_path)).fx(afx.volumex, soundtrack_volume)
        if audio.duration < video.duration:
            audio = audio.fx(afx.audio_loop, duration=video.duration)
        else:
            audio = audio.subclip(0, video.duration)
        video = video.set_audio(audio)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    video.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac" if soundtrack_path is not None else None,
        threads=4,
        preset="medium",
    )

    for clip in clips:
        clip.close()
    video.close()
