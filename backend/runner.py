from __future__ import annotations

import traceback
import uuid
from collections.abc import Callable
from pathlib import Path

from backend.models.job import JobStatus
from backend.pipeline.extract import extract_content, save_extracted
from backend.pipeline.render import render_video
from backend.pipeline.script import build_script, save_script
from backend.pipeline.summarize import save_summary, summarize_content
from backend.pipeline.tts import generate_tts


def new_job_dir(base_dir: Path, job_id: str | None = None) -> tuple[str, Path]:
    job_id = job_id or str(uuid.uuid4())
    job_dir = base_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_id, job_dir


ProgressCallback = Callable[[JobStatus, int, str | None], None]


def run_pipeline(
    url: str,
    job_dir: Path,
    on_progress: ProgressCallback | None = None,
    voice: str | None = None,
) -> dict:
    def update(status: JobStatus, progress: int, error: str | None = None):
        if on_progress:
            on_progress(status, progress, error)

    try:
        update(JobStatus.EXTRACTING, 10)
        extracted = extract_content(url)
        save_extracted(job_dir, extracted)

        update(JobStatus.SUMMARIZING, 25)
        summary = summarize_content(extracted)
        save_summary(job_dir, summary)

        update(JobStatus.SCRIPTING, 40)
        script = build_script(extracted, summary)
        save_script(job_dir, script)

        update(JobStatus.TTS_GENERATING, 55)
        generate_tts(job_dir, script, voice=voice)

        update(JobStatus.RENDERING, 75)
        output = render_video(job_dir)

        update(JobStatus.READY, 100)
        return {
            "output": str(output),
            "caption": summary.caption,
            "hashtags": summary.hashtags,
            "title": extracted.title,
        }
    except Exception as exc:
        update(JobStatus.FAILED, 0, str(exc))
        traceback.print_exc()
        raise
