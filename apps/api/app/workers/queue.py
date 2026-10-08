"""SQLite job queue (S13): enqueue, claim, complete/fail, retry, cancel.

Single-worker semantics: claim_next atomically moves one due QUEUED job to
RUNNING (UPDATE..WHERE status=QUEUED guards races). Backoff uses
next_run_at so failed jobs don't hammer the worker. Dedupe on exact
(type, payload) while a matching job is QUEUED/RUNNING (idempotency key).
"""

import json
import structlog
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.db import models

log = structlog.get_logger()

TERMINAL = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
MAX_ATTEMPTS = 5


class JobError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue(db: Session, job_type: str, payload: dict | None = None,
            priority: int = 30) -> models.Job:
    """Enqueue unless an identical job is already QUEUED/RUNNING (dedupe)."""
    blob = json.dumps(payload or {}, sort_keys=True)
    existing = (
        db.query(models.Job)
        .filter(models.Job.type == job_type,
                models.Job.payload_json == blob,
                models.Job.status.in_(("QUEUED", "RUNNING")))
        .order_by(models.Job.id.desc()).first()
    )
    if existing is not None:
        log.info("job_deduped", job_id=existing.id, type=job_type)
        return existing
    job = models.Job(type=job_type, status="QUEUED", priority=priority,
                     payload_json=blob)
    db.add(job)
    db.flush()
    log.info("job_enqueued", job_id=job.id, type=job_type, priority=priority)
    return job


def claim_next(db: Session) -> models.Job | None:
    """Atomically claim the highest-priority due job (None when empty)."""
    row = (
        db.query(models.Job)
        .filter(models.Job.status == "QUEUED",
                ((models.Job.next_run_at.is_(None))
                 | (models.Job.next_run_at <= _now())))
        .order_by(models.Job.priority.desc(), models.Job.id.asc())
        .first()
    )
    if row is None:
        return None
    updated = (
        db.query(models.Job)
        .filter(models.Job.id == row.id,
                models.Job.status == "QUEUED")
        .update({"status": "RUNNING", "started_at": _now()},
                synchronize_session=False)
    )
    db.flush()
    if not updated:
        return None
    db.refresh(row)
    log.info("job_claimed", job_id=row.id, type=row.type)
    return row


def complete(db: Session, job: models.Job, result: dict | None = None) -> None:
    job.status = "COMPLETED"
    job.progress = 1.0
    if result is not None:
        job.payload_json = json.dumps(
            {**json.loads(job.payload_json), "result": result})
    job.completed_at = _now()
    db.flush()
    log.info("job_completed", job_id=job.id, type=job.type)


def fail(db: Session, job: models.Job, error: str) -> None:
    job.status = "FAILED"
    job.attempts = (job.attempts or 0) + 1
    job.error = error[:2000]
    job.completed_at = _now()
    # exponential backoff before a retry may run
    backoff = min(2 ** max(job.attempts - 1, 0), 60)
    job.next_run_at = _now() + timedelta(minutes=backoff)
    db.flush()
    log.info("job_failed", job_id=job.id, type=job.type,
             attempts=job.attempts, error=error[:200])


def retry(db: Session, job_id: int) -> models.Job:
    job = db.get(models.Job, job_id)
    if job is None:
        raise JobError(f"job not found: {job_id}")
    if job.status not in ("FAILED", "CANCELLED"):
        raise JobError(f"job {job_id} is {job.status} — only FAILED/"
                       "CANCELLED jobs can be retried")
    job.status = "QUEUED"
    job.error = ""
    job.progress = 0.0
    job.next_run_at = None
    job.started_at = None
    job.completed_at = None
    db.flush()
    log.info("job_retried", job_id=job.id, type=job.type)
    return job


def cancel(db: Session, job_id: int) -> models.Job:
    job = db.get(models.Job, job_id)
    if job is None:
        raise JobError(f"job not found: {job_id}")
    if job.status != "QUEUED":
        raise JobError(f"job {job_id} is {job.status} — only QUEUED "
                       "jobs can be cancelled")
    job.status = "CANCELLED"
    job.completed_at = _now()
    db.flush()
    return job


def priority_for_velocity(velocity: float) -> int:
    """Dynamic priority bands: BREAKING 100 / RISING 70 / NORMAL 30 / OLD 5."""
    if velocity >= 5000:
        return 100
    if velocity >= 1000:
        return 70
    if velocity >= 100:
        return 30
    return 5
