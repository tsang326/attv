from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import edge_tts

from backend.config import settings
from backend.pipeline.script import ScriptResult, load_script


@dataclass
class SlideTiming:
    index: int
    text: str
    start: float
    end: float
    audio_file: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TTSResult:
    voiceover_path: str
    timings: list[SlideTiming]
    total_duration: float

    def to_dict(self) -> dict:
        return {
            "voiceover_path": self.voiceover_path,
            "timings": [t.to_dict() for t in self.timings],
            "total_duration": self.total_duration,
        }


async def _generate_clip(text: str, output: Path, voice: str) -> float:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output))

    from moviepy import AudioFileClip

    with AudioFileClip(str(output)) as clip:
        return float(clip.duration)


async def generate_tts_async(job_dir: Path, script: ScriptResult, voice: str | None = None) -> TTSResult:
    voice = voice or settings.tts_voice
    audio_dir = job_dir / "audio"
    audio_dir.mkdir(exist_ok=True)

    timings: list[SlideTiming] = []
    current = 0.0
    clip_paths: list[Path] = []

    for i, slide in enumerate(script.slides):
        clip_path = audio_dir / f"slide_{i:02d}.mp3"
        duration = await _generate_clip(slide.text, clip_path, voice)
        end = current + duration
        timings.append(
            SlideTiming(index=i, text=slide.text, start=current, end=end, audio_file=str(clip_path))
        )
        clip_paths.append(clip_path)
        current = end + 0.3

    voiceover_path = job_dir / "voiceover.mp3"
    await _merge_audio_clips(clip_paths, voiceover_path)

    return TTSResult(voiceover_path=str(voiceover_path), timings=timings, total_duration=current)


async def _merge_audio_clips(clip_paths: list[Path], output: Path) -> None:
    if not clip_paths:
        return
    if len(clip_paths) == 1:
        output.write_bytes(clip_paths[0].read_bytes())
        return

    from moviepy import AudioFileClip, concatenate_audioclips

    clips = [AudioFileClip(str(p)) for p in clip_paths]
    try:
        merged = concatenate_audioclips(clips)
        merged.write_audiofile(str(output), logger=None)
        merged.close()
    finally:
        for clip in clips:
            clip.close()


def generate_tts(job_dir: Path, script: ScriptResult | None = None, voice: str | None = None) -> TTSResult:
    script = script or load_script(job_dir)
    result = asyncio.run(generate_tts_async(job_dir, script, voice))
    save_tts(job_dir, result)
    return result


def save_tts(job_dir: Path, result: TTSResult) -> Path:
    path = job_dir / "timings.json"
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_tts(job_dir: Path) -> TTSResult:
    data = json.loads((job_dir / "timings.json").read_text(encoding="utf-8"))
    timings = [SlideTiming(**t) for t in data["timings"]]
    return TTSResult(
        voiceover_path=data["voiceover_path"],
        timings=timings,
        total_duration=data["total_duration"],
    )
