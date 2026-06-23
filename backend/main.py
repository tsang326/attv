from __future__ import annotations

import asyncio
import json
import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, HttpUrl

from backend.config import settings
from backend.database import init_db
from backend.models.job import Job, JobStatus
from backend.pipeline.publish import (
    exchange_code_for_token,
    get_auth_url,
    get_creator_info,
    is_tiktok_configured,
    publish_to_tiktok,
)
from backend.worker import create_job, get_job, list_jobs, process_job, process_scheduled_jobs

async def _scheduler_loop() -> None:
    while True:
        try:
            await process_scheduled_jobs()
        except Exception:
            pass
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    await init_db()
    scheduler = asyncio.create_task(_scheduler_loop())
    yield
    scheduler.cancel()


app = FastAPI(title="ATTV API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_tiktok_states: dict[str, str] = {}
_tiktok_tokens_path = Path("data/tiktok_tokens.json")


class CreateJobRequest(BaseModel):
    url: HttpUrl
    voice: str | None = None
    scheduled_at: datetime | None = None


class BatchJobRequest(BaseModel):
    urls: list[HttpUrl] = Field(min_length=1)
    voice: str | None = None


class PublishRequest(BaseModel):
    privacy_level: str = "SELF_ONLY"
    mode: str = "inbox"
    caption: str | None = None


def _job_to_dict(job: Job) -> dict:
    return {
        "id": job.id,
        "url": job.url,
        "status": job.status.value,
        "progress": job.progress,
        "error": job.error,
        "job_dir": job.job_dir,
        "meta": job.meta or {},
        "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "output_url": f"/jobs/{job.id}/video" if job.status == JobStatus.READY else None,
    }


def _load_tiktok_tokens() -> dict:
    if _tiktok_tokens_path.exists():
        return json.loads(_tiktok_tokens_path.read_text(encoding="utf-8"))
    return {}


def _save_tiktok_tokens(data: dict) -> None:
    _tiktok_tokens_path.parent.mkdir(parents=True, exist_ok=True)
    _tiktok_tokens_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/health")
async def health():
    return {"status": "ok", "tiktok_configured": is_tiktok_configured()}


@app.post("/jobs")
async def create_job_endpoint(body: CreateJobRequest, background_tasks: BackgroundTasks):
    job = await create_job(str(body.url), scheduled_at=body.scheduled_at)
    if body.scheduled_at:
        return _job_to_dict(job)
    background_tasks.add_task(process_job, job.id, body.voice)
    return _job_to_dict(job)


@app.post("/jobs/batch")
async def create_batch_endpoint(body: BatchJobRequest, background_tasks: BackgroundTasks):
    jobs = []
    for url in body.urls:
        job = await create_job(str(url))
        jobs.append(job)
        background_tasks.add_task(process_job, job.id, body.voice)
    return [_job_to_dict(j) for j in jobs]


@app.get("/jobs")
async def list_jobs_endpoint(limit: int = Query(50, ge=1, le=200)):
    jobs = await list_jobs(limit=limit)
    return [_job_to_dict(j) for j in jobs]


@app.get("/jobs/{job_id}")
async def get_job_endpoint(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)


@app.get("/jobs/{job_id}/video")
async def get_job_video(job_id: str):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    video = Path(job.job_dir) / "output.mp4"
    if not video.exists():
        raise HTTPException(status_code=404, detail="Video not ready")
    return FileResponse(video, media_type="video/mp4", filename=f"{job_id}.mp4")


@app.post("/jobs/{job_id}/publish")
async def publish_job(job_id: str, body: PublishRequest):
    job = await get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in (JobStatus.READY, JobStatus.PUBLISHED):
        raise HTTPException(status_code=400, detail=f"Job not ready: {job.status}")

    tokens = _load_tiktok_tokens()
    access_token = tokens.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="TikTok not connected. Visit /auth/tiktok")

    caption = body.caption or (job.meta or {}).get("caption", "Video from ATTV")
    try:
        result = publish_to_tiktok(
            access_token=access_token,
            job_dir=Path(job.job_dir),
            caption=caption,
            privacy_level=body.privacy_level,
            mode=body.mode,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    from backend.worker import _update_job

    await _update_job(job_id, JobStatus.PUBLISHED, 100, meta={"publish": result})
    return {"job_id": job_id, "result": result}


@app.get("/auth/tiktok")
async def tiktok_auth():
    if not is_tiktok_configured():
        raise HTTPException(status_code=400, detail="TikTok credentials not configured in .env")
    state = secrets.token_urlsafe(16)
    _tiktok_states[state] = state
    return RedirectResponse(get_auth_url(state))


@app.get("/auth/tiktok/callback")
async def tiktok_callback(code: str, state: str):
    if state not in _tiktok_states:
        raise HTTPException(status_code=400, detail="Invalid state")
    del _tiktok_states[state]

    token_data = exchange_code_for_token(code)
    data = token_data.get("data", token_data)
    _save_tiktok_tokens(data)
    return {"message": "TikTok connected", "open_id": data.get("open_id")}


@app.get("/auth/tiktok/status")
async def tiktok_status():
    tokens = _load_tiktok_tokens()
    if not tokens.get("access_token"):
        return {"connected": False}
    try:
        info = get_creator_info(tokens["access_token"])
        return {"connected": True, "creator_info": info}
    except Exception as exc:
        return {"connected": True, "error": str(exc)}
