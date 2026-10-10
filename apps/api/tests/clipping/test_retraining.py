"""D13 retraining cadence: policy gates, holdout acceptance, audit trail."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.domain.clipping import retraining


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _label(db, ext: str, hook: float, decision: str) -> None:
    src = models.Source(provider="youtube", external_id=ext, url="")
    db.add(src)
    db.flush()
    m = models.Moment(source_id=src.id, start_time=0.0, end_time=8.0,
                      transcript_excerpt="t", final_score=50.0,
                      features_json=json.dumps({"hook": hook, "emotion": 0.0}))
    db.add(m)
    db.flush()
    db.add(models.MomentFeedback(
        moment_id=m.id, decision=decision, reason="t",
        original_start=0.0, original_end=8.0,
        adjusted_start=0.0, adjusted_end=8.0))
    db.flush()


def _seed(db, n_pos=7, n_neg=5, prefix="d13"):
    for i in range(n_pos):
        _label(db, f"{prefix}-a{i}", 1.0, "APPROVED")
    for i in range(n_neg):
        _label(db, f"{prefix}-r{i}", 0.0, "REJECTED")
    db.commit()


CFG = {
    "enabled": True, "min_new_labels": 5, "min_interval_hours": 24,
    "min_rows": 10, "min_holdout_accuracy": 0.6, "min_holdout_auc": 0.6,
    "require_improvement": False, "output": "ret_ranker.json",
}


def _cfg(tmp_path, **overrides):
    cfg = dict(CFG)
    cfg["output"] = str(tmp_path / "ret_ranker.json")
    cfg["require_improvement"] = True
    cfg.update(overrides)
    return cfg


def test_retrain_accepts_when_policy_met(db, tmp_path):
    _seed(db)
    out = retraining.maybe_retrain(db, cfg=_cfg(tmp_path))
    assert out["accepted"] is True
    assert out["holdout"]["accuracy"] >= 0.6
    assert (tmp_path / "ret_ranker.json").is_file()
    run = db.query(models.RankerRun).one()
    assert run.accepted is True and run.rows == 12


def test_retrain_refuses_when_too_few_new_labels(db, tmp_path):
    _seed(db)
    retraining.maybe_retrain(db, cfg=_cfg(tmp_path))
    # same labels as last accepted run -> nothing new
    out = retraining.maybe_retrain(db, cfg=_cfg(tmp_path))
    assert out["accepted"] is False
    assert "new labels" in out["reason"]
    assert db.query(models.RankerRun).count() == 2  # first + refusal


def test_retrain_refuses_when_interval_not_elapsed(db, tmp_path):
    _seed(db)
    retraining.maybe_retrain(db, cfg=_cfg(tmp_path))
    _seed(db, n_pos=6, n_neg=4, prefix="more")  # 10 new labels: policy met
    out = retraining.maybe_retrain(db, cfg=_cfg(tmp_path))
    assert out["accepted"] is False
    assert "ago" in out["reason"]


def test_force_bypasses_policy(db, tmp_path):
    _seed(db)
    out = retraining.maybe_retrain(db, force=True, cfg=_cfg(tmp_path))
    assert out["accepted"] is True
    run = db.query(models.RankerRun).filter_by(forced=True).one()
    assert run.accepted is True


def test_retrain_refuses_single_class_data(db, tmp_path, monkeypatch):
    for i in range(12):
        _label(db, f"same{i}", 1.0, "APPROVED")
    db.commit()
    monkeypatch.chdir(tmp_path)
    out = retraining.maybe_retrain(db, cfg=CFG)
    assert out["accepted"] is False
    assert "both" in out["reason"]


def test_retrain_validates_and_keeps_old_weights(db, tmp_path):
    """Garbage-in labels must not overwrite a good weights file."""
    _seed(db)
    assert retraining.maybe_retrain(db, cfg=_cfg(tmp_path))["accepted"] is True
    good_path = tmp_path / "ret_ranker.json"
    before = good_path.read_text(encoding="utf-8")
    # now destroy the signal: scramble every other label so no consistent
    # policy exists (flipping ALL labels would still be learnable)
    for i, fb in enumerate(db.query(models.MomentFeedback).all()):
        if i % 2 == 0:
            fb.decision = "REJECTED" if fb.decision == "APPROVED" else "APPROVED"
    db.commit()
    out = retraining.maybe_retrain(
        db, force=True,
        cfg=_cfg(tmp_path, require_improvement=False,
                 min_holdout_accuracy=0.99, min_holdout_auc=0.99))
    assert out["accepted"] is False
    assert good_path.read_text(encoding="utf-8") == before


def test_no_improvement_refused_but_kept_for_audit(db, tmp_path):
    _seed(db)
    first = retraining.maybe_retrain(db, cfg=_cfg(tmp_path))
    assert first["accepted"] is True
    # retrain on the same data with fresh rows -> accuracy ties at best
    second = retraining.maybe_retrain(db, force=True, cfg=_cfg(tmp_path))
    assert second["accepted"] is False
    assert "no improvement" in second["reason"]


def test_status_shape(db, tmp_path):
    _seed(db, n_pos=2, n_neg=1)
    status = retraining.state(db, cfg=_cfg(tmp_path))
    assert status["labels"] == 3
    assert status["weights_present"] is False
    assert status["last_run"] is None
    assert status["weights_file"].endswith("ret_ranker.json")


def test_retrain_routes(db, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool

    from app.db.database import get_db
    from app.main import create_app

    # keep the route-level run inside the tmp dir (never the repo checkout)
    monkeypatch.setattr(
        retraining, "_cfg",
        lambda: {**CFG,
                 "output": str(tmp_path / "api_ranker.json"),
                 "require_improvement": False})
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool

    from app.db.database import get_db
    from app.main import create_app

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    for i in range(7):
        sid = client.post("/api/v1/sources", json={
            "external_id": f"api-a{i}", "title": "x"}).json()["id"]
        db2 = factory()
        db2.execute(models.Moment.__table__.insert().values(
            source_id=sid, start_time=0.0, end_time=8.0,
            transcript_excerpt="t", final_score=50.0,
            features_json=json.dumps({"hook": 1.0})))
        db2.commit()
        mid = db2.execute(models.Moment.__table__.select()).fetchall()[-1][0]
        db2.add(models.MomentFeedback(
            moment_id=mid, decision="APPROVED", reason="x",
            original_start=0.0, original_end=8.0,
            adjusted_start=0.0, adjusted_end=8.0))
        db2.commit()
        db2.close()
    for i in range(5):
        sid = client.post("/api/v1/sources", json={
            "external_id": f"api-r{i}", "title": "x"}).json()["id"]
        db2 = factory()
        db2.execute(models.Moment.__table__.insert().values(
            source_id=sid, start_time=0.0, end_time=8.0,
            transcript_excerpt="t", final_score=50.0,
            features_json=json.dumps({"hook": 0.0})))
        db2.commit()
        mid = db2.execute(models.Moment.__table__.select()).fetchall()[-1][0]
        db2.add(models.MomentFeedback(
            moment_id=mid, decision="REJECTED", reason="x",
            original_start=0.0, original_end=8.0,
            adjusted_start=0.0, adjusted_end=8.0))
        db2.commit()
        db2.close()

    body = client.get("/api/v1/ranker/status").json()
    assert body["labels"] == 12
    monkeypatch.chdir(tmp_path)
    r = client.post("/api/v1/ranker/retrain",
                    json={"force": True}).json()
    assert r["accepted"] is True
    assert client.get("/api/v1/ranker/status").json()["last_run"][
        "accepted"] is True
