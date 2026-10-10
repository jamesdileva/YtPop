"""Interval scheduler (S13): 15m scores, 30m analysis drain, 60m cluster.

tick() is pure logic (testable with any clock); the background loop runs it
every loop_seconds when YTPOP_SCHEDULER=true. A task is due when no
QUEUED/RUNNING/COMPLETED job of its type was created inside its interval —
recent FAILED jobs don't block the next attempt (self-healing).
"""

import structlog
import threading
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.workers import queue as q

log = structlog.get_logger()

DEFAULT_SCHEDULER: dict = {
    "score_refresh_minutes": 15,
    "drain_minutes": 30,
    "cluster_minutes": 60,
    "retrain_hours": 24,
    "loop_seconds": 60,
}

# (job type, payload, config key). Keys ending in _minutes are read as
# minutes, _hours as hours.
TASKS: tuple[tuple[str, dict, str], ...] = (
    ("REFRESH_SCORES", {}, "score_refresh_minutes"),
    ("DRAIN_ANALYSIS", {"limit": 5}, "drain_minutes"),
    ("CLUSTER", {"region": "US"}, "cluster_minutes"),
    ("RETRAIN", {}, "retrain_hours"),
)


def _interval(key: str, schedule: dict) -> timedelta:
    value = float(schedule[key])
    if key.endswith("_hours"):
        return timedelta(hours=value)
    return timedelta(minutes=value)

_thread: threading.Thread | None = None


def load_schedule(path: str | Path | None = None) -> dict:
    cfg = deepcopy(DEFAULT_SCHEDULER)
    if path is None:
        from app.db.database import repo_root

        candidate = repo_root() / "configs" / "default.yaml"
    else:
        candidate = Path(path)
    if candidate.is_file():
        with open(candidate, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        cfg.update(loaded.get("scheduler") or {})
    return cfg


def _last_run(db: Session, job_type: str) -> datetime | None:
    from app.db import models

    row = (
        db.query(models.Job)
        .filter(models.Job.type == job_type,
                models.Job.status.in_(("QUEUED", "RUNNING", "COMPLETED")))
        .order_by(models.Job.id.desc()).first()
    )
    if row is None or row.created_at is None:
        return None
    created = row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return created


def tick(db: Session, now: datetime | None = None,
         schedule: dict | None = None) -> dict:
    """Enqueue due periodic tasks. Returns what was enqueued."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    schedule = schedule or load_schedule()
    enqueued: list[str] = []
    for job_type, payload, interval_key in TASKS:
        interval = _interval(interval_key, schedule)
        last = _last_run(db, job_type)
        if last is not None and (now - last) < interval:
            continue
        q.enqueue(db, job_type, dict(payload), priority=30)
        enqueued.append(job_type)
        log.info("scheduler_enqueued", type=job_type,
                 episode="n/a", job="n/a", source="n/a", stage="scheduler")
    db.commit()
    return {"ticked_at": now.isoformat(), "enqueued": enqueued}


def _loop() -> None:
    from app.db.database import get_session_factory

    while True:
        try:
            db = get_session_factory()()
            try:
                result = tick(db)
                if result["enqueued"]:
                    log.info("scheduler_tick", **result)
            finally:
                db.close()
        except Exception as e:
            log.error("scheduler_error", error=str(e)[:300])
        try:
            interval = float(load_schedule()["loop_seconds"])
        except Exception:
            interval = 60.0
        time.sleep(max(interval, 10.0))


def start_background_loop() -> bool:
    """Start the daemon scheduler thread (once per process)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return False
    _thread = threading.Thread(target=_loop, name="ytpop-scheduler",
                               daemon=True)
    _thread.start()
    log.info("scheduler_started")
    return True
