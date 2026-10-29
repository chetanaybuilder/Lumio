import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from app.db.models import IngestionJob, Document

async def claim_next_job(db: AsyncSession, worker_id: str) -> Optional[IngestionJob]:
    """
    Claims the next queued job using SKIP LOCKED.
    Increments attempts, sets status='running', locked_by, heartbeat_at.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(IngestionJob)
        .where(
            IngestionJob.status == "queued",
            IngestionJob.run_after <= now
        )
        .order_by(IngestionJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        return None

    job.status = "running"
    job.locked_by = worker_id
    job.heartbeat_at = now
    job.attempts += 1
    await db.commit()
    await db.refresh(job)
    return job

async def heartbeat_job(db: AsyncSession, job_id: uuid.UUID):
    """Updates heartbeat timestamp every 15s."""
    now = datetime.now(timezone.utc)
    await db.execute(
        update(IngestionJob).where(IngestionJob.id == job_id).values(heartbeat_at=now)
    )
    await db.commit()

async def reap_stale_jobs(db: AsyncSession):
    """Requeues running jobs whose heartbeat is older than 2 minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
    stmt = (
        update(IngestionJob)
        .where(
            IngestionJob.status == "running",
            IngestionJob.heartbeat_at < cutoff
        )
        .values(status="queued", locked_by=None)
    )
    await db.execute(stmt)
    await db.commit()
