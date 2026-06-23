from __future__ import annotations

import textwrap
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

from backend.pipeline.script import ScriptResult, load_script
from backend.pipeline.tts import TTSResult, load_tts

VIDEO_W = 1080
VIDEO_H = 1920
FPS = 30


def _download_image(url: str) -> Image.Image:
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGB")
    return img


def _fit_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    img_ratio = img.width / img.height
    target_ratio = width / height
    if img_ratio > target_ratio:
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    else:
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))
    return img.resize((width, height), Image.Resampling.LANCZOS)


def _gradient_background(width: int, height: int, color1=(20, 24, 48), color2=(45, 55, 95)) -> Image.Image:
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / height
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return img


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _render_slide_frame(slide_text: str, image_url: str, subtitle: str) -> Image.Image:
    try:
        bg = _fit_cover(_download_image(image_url), VIDEO_W, VIDEO_H)
    except Exception:
        bg = _gradient_background(VIDEO_W, VIDEO_H)

    overlay = Image.new("RGBA", (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([(0, 0), (VIDEO_W, VIDEO_H)], fill=(0, 0, 0, 90))
    draw.rectangle([(60, 120), (VIDEO_W - 60, 420)], fill=(0, 0, 0, 160))

    title_font = _get_font(52)
    subtitle_font = _get_font(40)

    title_lines = textwrap.wrap(slide_text, width=28)[:3]
    y = 150
    for line in title_lines:
        draw.text((90, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += 62

    sub_lines = textwrap.wrap(subtitle, width=32)[:2]
    sub_y = VIDEO_H - 280
    draw.rectangle([(40, sub_y - 30), (VIDEO_W - 40, VIDEO_H - 80)], fill=(0, 0, 0, 180))
    for line in sub_lines:
        draw.text((70, sub_y), line, font=subtitle_font, fill=(255, 255, 200, 255))
        sub_y += 50

    composed = Image.alpha_composite(bg.convert("RGBA"), overlay)
    return composed.convert("RGB")


def _ken_burns_clip(frame_path: Path, duration: float):
    from moviepy import ImageClip

    base = ImageClip(str(frame_path)).with_duration(duration)

    def scale(t: float) -> float:
        return 1.0 + 0.06 * (t / max(duration, 0.1))

    try:
        return base.resized(scale)
    except Exception:
        return base


def render_video(job_dir: Path, script: ScriptResult | None = None, tts: TTSResult | None = None) -> Path:
    from moviepy import AudioFileClip, concatenate_videoclips

    script = script or load_script(job_dir)
    tts = tts or load_tts(job_dir)
    frames_dir = job_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    clips = []
    for i, slide in enumerate(script.slides):
        timing = tts.timings[i]
        duration = max(timing.end - timing.start, 2.5)
        frame_path = frames_dir / f"slide_{i:02d}.png"
        frame = _render_slide_frame(slide.text, slide.image_url, slide.text)
        frame.save(frame_path)
        clip = _ken_burns_clip(frame_path, duration)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    audio = AudioFileClip(tts.voiceover_path)
    video = video.with_audio(audio)
    if video.duration > audio.duration:
        video = video.subclipped(0, audio.duration)

    output = job_dir / "output.mp4"
    video.write_videofile(
        str(output),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        logger=None,
    )
    video.close()
    audio.close()
    return output
