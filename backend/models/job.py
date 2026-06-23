from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    SUMMARIZING = "summarizing"
    SCRIPTING = "scripting"
    TTS_GENERATING = "tts_generating"
    RENDERING = "rendering"
    READY = "ready"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    SCHEDULED = "scheduled"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.QUEUED)
    progress: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_dir: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
