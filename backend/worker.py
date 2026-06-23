from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from backend.config import settings
from backend.database import SessionLocal, init_db
from backend.models.job import Job, JobStatus
from backend.runner import new_job_dir, run_pipeline


async def create_job(url: str, scheduled_at: datetime | None = None) -> Job:
    job_id, job_dir = new_job_dir(settings.data_dir)
    async with SessionLocal() as session:
        job = Job(
            id=job_id,
            url=url,
            status=JobStatus.SCHEDULED if scheduled_at else JobStatus.QUEUED,
            progress=0,
            job_dir=str(job_dir),
            meta={},
            scheduled_at=scheduled_at,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


async def get_job(job_id: str) -> Job | None:
    async with SessionLocal() as session:
        result = await session.execute(select(Job).where(Job.id == job_id))
        return result.scalar_one_or_none()


async def list_jobs(limit: int = 50) -> list[Job]:
    async with SessionLocal() as session:
        result = await session.execute(select(Job).order_by(Job.created_at.desc()).limit(limit))
        return list(result.scalars().all())


async def _update_job(job_id: str, status: JobStatus, progress: int, error: str | None = None, meta: dict | None = None):
    async with SessionLocal() as session:
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one()
        job.status = status
        job.progress = progress
        job.error = error
        if meta:
            job.meta = {**(job.meta or {}), **meta}
        await session.commit()


def _run_pipeline_sync(job_id: str, url: str, job_dir: str, voice: str | None = None):
    def on_progress(status: JobStatus, progress: int, error: str | None = None):
        asyncio.run(_update_job(job_id, status, progress, error))

    result = run_pipeline(url, Path(job_dir), on_progress=on_progress, voice=voice)
    asyncio.run(_update_job(job_id, JobStatus.READY, 100, meta=result))


async def process_job(job_id: str, voice: str | None = None) -> None:
    job = await get_job(job_id)
    if not job:
        raise ValueError(f"Job not found: {job_id}")

    await _update_job(job_id, JobStatus.QUEUED, 5)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_pipeline_sync, job_id, job.url, job.job_dir, voice)


async def process_scheduled_jobs() -> None:
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        result = await session.execute(
            select(Job).where(Job.status == JobStatus.SCHEDULED, Job.scheduled_at <= now)
        )
        jobs = list(result.scalars().all())

    for job in jobs:
        await process_job(job.id)


async def create_and_run_job(url: str, voice: str | None = None) -> Job:
    await init_db()
    job = await create_job(url)
    asyncio.create_task(process_job(job.id, voice=voice))
    return job


async def create_batch_jobs(urls: list[str], voice: str | None = None) -> list[Job]:
    await init_db()
    jobs = []
    for url in urls:
        job = await create_job(url.strip())
        jobs.append(job)
        asyncio.create_task(process_job(job.id, voice=voice))
    return jobs
