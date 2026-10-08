"""S13 job queue + scheduler + jobs routes tests."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.main import create_app
from app.workers import handlers, queue as q
from app.workers import scheduler as sched


@pytest.fixture()
def setup():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    return TestClient(app), factory


def test_enqueue_dedupes(setup):
    _, factory = setup
    db = factory()
    a = q.enqueue(db, "CLUSTER", {"region": "US"})
    b = q.enqueue(db, "CLUSTER", {"region": "US"})
    assert a.id == b.id
    c = q.enqueue(db, "CLUSTER", {"region": "EU"})
    assert c.id != a.id
    db.close()


def test_claim_priority_order_and_backoff(setup):
    _, factory = setup
    db = factory()
    lo = q.enqueue(db, "CLUSTER", {"n": 1}, priority=5)
    hi = q.enqueue(db, "CLUSTER", {"n": 2}, priority=100)
    assert q.claim_next(db).id == hi.id
    assert q.claim_next(db).id == lo.id
    assert q.claim_next(db) is None
    # FAILED jobs are not claimable; retry requeues with backoff gating
    q.fail(db, hi, "boom")
    assert q.claim_next(db) is None
    q.retry(db, hi.id)
    hi.next_run_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    db.flush()
    assert q.claim_next(db) is None
    hi.next_run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.flush()
    claimed = q.claim_next(db)
    assert claimed is not None and claimed.id == hi.id
    db.close()


def test_complete_fail_retry_cancel(setup):
    _, factory = setup
    db = factory()
    job = q.enqueue(db, "REFRESH_SCORES", {})
    q.complete(db, job, {"updated": 0})
    assert job.status == "COMPLETED" and job.progress == 1.0
    with pytest.raises(q.JobError, match="only FAILED"):
        q.retry(db, job.id)
    with pytest.raises(q.JobError, match="only QUEUED"):
        q.cancel(db, job.id)
    bad = q.enqueue(db, "REFRESH_SCORES", {"x": 1})
    q.fail(db, bad, "err")
    assert bad.attempts == 1 and bad.next_run_at is not None
    q.retry(db, bad.id)
    assert bad.status == "QUEUED" and bad.next_run_at is None
    q.cancel(db, bad.id)
    assert bad.status == "CANCELLED"
    with pytest.raises(q.JobError, match="not found"):
        q.retry(db, 9999)
    db.close()


def test_priority_bands():
    assert q.priority_for_velocity(9000) == 100
    assert q.priority_for_velocity(2000) == 70
    assert q.priority_for_velocity(500) == 30
    assert q.priority_for_velocity(10) == 5


def test_run_refresh_scores(setup):
    _, factory = setup
    db = factory()
    db.add(models.Source(provider="youtube", external_id="j",
                         url="", view_count=1000))
    db.commit()
    job = q.enqueue(db, "REFRESH_SCORES", {})
    db.commit()
    result = handlers.run_job(db, job.id, handlers.Ctx())
    assert result == {"updated": 1}
    assert db.get(models.Job, job.id).status == "COMPLETED"
    db.close()


def test_run_unknown_type_fails(setup):
    _, factory = setup
    db = factory()
    job = models.Job(type="NOPE", status="QUEUED", payload_json="{}")
    db.add(job)
    db.commit()
    with pytest.raises(q.JobError, match="unknown job type"):
        handlers.run_job(db, job.id, handlers.Ctx())
    assert db.get(models.Job, job.id).status == "FAILED"
    db.close()


def test_run_discover_without_key_fails_cleanly(setup, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "youtube_api_key", "")
    _, factory = setup
    db = factory()
    job = q.enqueue(db, "DISCOVER", {"region": "US"})
    db.commit()
    with pytest.raises(q.JobError, match="not configured"):
        handlers.run_job(db, job.id, handlers.Ctx())
    row = db.get(models.Job, job.id)
    assert row.status == "FAILED" and "not configured" in row.error
    db.close()


def test_scheduler_tick_and_intervals(setup):
    _, factory = setup
    db = factory()
    first = sched.tick(db)
    assert sorted(first["enqueued"]) == ["CLUSTER", "DRAIN_ANALYSIS",
                                        "REFRESH_SCORES"]
    second = sched.tick(db)
    assert second["enqueued"] == []
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    third = sched.tick(db, now=future)
    assert sorted(third["enqueued"]) == ["CLUSTER", "DRAIN_ANALYSIS",
                                        "REFRESH_SCORES"]
    db.close()


def test_scheduler_status_endpoint(setup):
    client, _ = setup
    body = client.get("/api/v1/scheduler/status").json()
    assert body["schedule"]["score_refresh_minutes"] == 15
    assert set(body["last_runs"]) == {"REFRESH_SCORES", "DRAIN_ANALYSIS",
                                      "CLUSTER"}
    r = client.post("/api/v1/scheduler/tick").json()
    assert len(r["enqueued"]) == 3


def test_jobs_routes(setup):
    client, _ = setup
    assert client.post("/api/v1/jobs",
                       json={"type": "NOPE"}).status_code == 400
    job = client.post("/api/v1/jobs",
                      json={"type": "REFRESH_SCORES"}).json()
    assert job["status"] == "QUEUED"
    listed = client.get("/api/v1/jobs").json()
    assert listed["queue_depth"]["QUEUED"] == 1
    assert client.get(f"/api/v1/jobs/{job['id']}").status_code == 200
    assert client.get("/api/v1/jobs/999").status_code == 404
    ran = client.post(f"/api/v1/jobs/{job['id']}/run").json()
    assert ran["status"] == "COMPLETED"
    # running again conflicts (already terminal)
    assert client.post(f"/api/v1/jobs/{job['id']}/run").status_code == 409
    assert client.post(f"/api/v1/jobs/{job['id']}/retry").status_code == 409
    assert client.post(f"/api/v1/jobs/{job['id']}/cancel").status_code == 409
    bad = client.post("/api/v1/jobs",
                      json={"type": "DISCOVER"}).json()
    assert client.post(f"/api/v1/jobs/{bad['id']}/run").status_code == 409
    retried = client.post(f"/api/v1/jobs/{bad['id']}/retry").json()
    assert retried["status"] == "QUEUED"
    cancelled = client.post(f"/api/v1/jobs/{bad['id']}/cancel").json()
    assert cancelled["status"] == "CANCELLED"


def test_pipeline_empty_db_400(setup):
    client, _ = setup
    r = client.post("/api/v1/pipeline/daily-episode", json={})
    assert r.status_code == 400
    assert "no trends" in r.json()["detail"]
