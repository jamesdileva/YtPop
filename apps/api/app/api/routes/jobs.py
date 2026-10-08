"""Jobs + pipeline routes (S13): queue ops and one-button episodes."""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.db.database import get_db
from app.workers import handlers, orchestrator, queue as q
from app.workers import scheduler as sched

log = structlog.get_logger()
router = APIRouter()


def _brief(row: models.Job) -> dict:
    return {
        "id": row.id, "type": row.type, "status": row.status,
        "priority": row.priority, "payload": row.payload_json,
        "progress": row.progress, "attempts": row.attempts,
        "error": row.error,
    }


class EnqueueRequest(BaseModel):
    type: str = Field(min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)
    priority: int = Field(default=30, ge=0, le=200)


@router.post("/jobs")
def enqueue_job(payload: EnqueueRequest,
                db: Session = Depends(get_db)) -> dict:
    if payload.type not in handlers.HANDLERS:
        raise HTTPException(
            status_code=400,
            detail=f"unknown job type {payload.type!r}, "
                   f"one of {sorted(handlers.HANDLERS)}")
    job = q.enqueue(db, payload.type, payload.payload, payload.priority)
    db.commit()
    return _brief(job)


@router.get("/jobs")
def list_jobs(status: str | None = None, job_type: str | None = None,
              limit: int = 100, db: Session = Depends(get_db)) -> dict:
    query = db.query(models.Job).order_by(models.Job.id.desc())
    if status is not None:
        query = query.filter_by(status=status)
    if job_type is not None:
        query = query.filter_by(type=job_type)
    rows = query.limit(max(limit, 1)).all()
    counts: dict[str, int] = {}
    for row in db.query(models.Job).all():
        counts[row.status] = counts.get(row.status, 0) + 1
    return {"jobs": [_brief(r) for r in rows], "queue_depth": counts}


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.get(models.Job, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _brief(row)


@router.post("/jobs/{job_id}/run")
def run_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        result = handlers.run_job(db, job_id)
    except q.JobError as e:
        msg = str(e)
        code = 404 if "not found" in msg else 409
        raise HTTPException(status_code=code, detail=msg) from e
    return {"job_id": job_id, "status": "COMPLETED", "result": result}


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        row = q.retry(db, job_id)
    except q.JobError as e:
        msg = str(e)
        code = 404 if "not found" in msg else 409
        raise HTTPException(status_code=code, detail=msg) from e
    db.commit()
    return _brief(row)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        row = q.cancel(db, job_id)
    except q.JobError as e:
        msg = str(e)
        code = 404 if "not found" in msg else 409
        raise HTTPException(status_code=code, detail=msg) from e
    db.commit()
    return _brief(row)


class DailyEpisodeRequest(BaseModel):
    trend: str = Field(default="", max_length=200)
    format: str = Field(default="daily_highlights", max_length=64)
    preset: str = Field(default="preview_720p", max_length=32)
    model: str = Field(default="", max_length=64)


@router.post("/pipeline/daily-episode")
def daily_episode(payload: DailyEpisodeRequest,
                  db: Session = Depends(get_db)) -> dict:
    try:
        return orchestrator.run_daily_episode(
            db, trend=payload.trend, format=payload.format,
            preset=payload.preset, model=payload.model)
    except orchestrator.PipelineError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/scheduler/tick")
def scheduler_tick(db: Session = Depends(get_db)) -> dict:
    return sched.tick(db)


@router.get("/scheduler/status")
def scheduler_status(db: Session = Depends(get_db)) -> dict:
    schedule = sched.load_schedule()
    last: dict[str, str | None] = {}
    for job_type, _, _ in sched.TASKS:
        run = sched._last_run(db, job_type)
        last[job_type] = run.isoformat() if run else None
    return {
        "enabled": settings.scheduler,
        "schedule": schedule,
        "last_runs": last,
    }
