"""S12 rights tests: state machine, publish blocker, expiry, demo mode."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.main import create_app


@pytest.fixture()
def setup(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
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


def _source(setup, ext="r1") -> int:
    client, _ = setup
    return client.post("/api/v1/sources", json={
        "external_id": ext, "title": "R",
    }).json()["id"]


def test_default_unknown_and_blocked(setup):
    client, _ = setup
    sid = _source(setup)
    assert client.get(f"/api/v1/rights/{sid}").json()["status"] == "UNKNOWN"
    check = client.get(f"/api/v1/rights/{sid}/publish-check").json()
    assert check["publishable"] is False
    assert any("UNKNOWN" in r for r in check["reasons"])
    assert client.get("/api/v1/rights/999").status_code == 404


def test_review_then_approve_with_reviewer(setup):
    client, _ = setup
    sid = _source(setup)
    assert client.post(f"/api/v1/rights/{sid}/review",
                       json={}).json()["status"] == "REVIEW_REQUIRED"
    # idempotent re-request
    assert client.post(f"/api/v1/rights/{sid}/review",
                       json={}).json()["status"] == "REVIEW_REQUIRED"
    # approval needs a human reviewer
    assert client.patch(f"/api/v1/rights/{sid}",
                        json={"status": "APPROVED"}).status_code == 400
    r = client.patch(f"/api/v1/rights/{sid}",
                     json={"status": "APPROVED", "reviewer": "ed",
                           "basis": "direct permission",
                           "permission_reference": "email 2026-10-07"})
    assert r.status_code == 200, r.text
    assert r.json()["reviewer"] == "ed"
    check = client.get(f"/api/v1/rights/{sid}/publish-check").json()
    assert check == {"source_id": sid, "status": "APPROVED",
                     "publishable": True, "reasons": []}


def test_illegal_jump_rejected(setup):
    client, _ = setup
    sid = _source(setup)
    # UNKNOWN → APPROVED skips review: forbidden
    r = client.patch(f"/api/v1/rights/{sid}",
                     json={"status": "APPROVED", "reviewer": "ed"})
    assert r.status_code == 400
    assert "illegal rights transition" in r.json()["detail"]


def test_needs_permission_flow(setup):
    client, _ = setup
    sid = _source(setup)
    client.post(f"/api/v1/rights/{sid}/review", json={})
    assert client.patch(
        f"/api/v1/rights/{sid}",
        json={"status": "NEEDS_PERMISSION"}).status_code == 200
    assert client.get(
        f"/api/v1/rights/{sid}/publish-check").json()["publishable"] is False
    r = client.patch(f"/api/v1/rights/{sid}",
                     json={"status": "PERMISSION_GRANTED",
                           "reviewer": "ed",
                           "permission_reference": "license-42"})
    assert r.status_code == 200
    assert client.get(
        f"/api/v1/rights/{sid}/publish-check").json()["publishable"] is True


def test_revoke_and_reopen(setup):
    client, _ = setup
    sid = _source(setup)
    client.post(f"/api/v1/rights/{sid}/review", json={})
    client.patch(f"/api/v1/rights/{sid}",
                 json={"status": "APPROVED", "reviewer": "ed"})
    assert client.patch(f"/api/v1/rights/{sid}",
                        json={"status": "REJECTED",
                              "reason": "takedown"}).status_code == 200
    assert client.get(
        f"/api/v1/rights/{sid}/publish-check").json()["publishable"] is False
    assert client.patch(f"/api/v1/rights/{sid}",
                        json={"status": "REVIEW_REQUIRED"}).status_code == 200


def test_expiry_blocks_publish(setup):
    client, _ = setup
    sid = _source(setup)
    client.post(f"/api/v1/rights/{sid}/review", json={})
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = client.patch(f"/api/v1/rights/{sid}",
                     json={"status": "APPROVED", "reviewer": "ed",
                           "expires_at": past})
    assert r.status_code == 200
    check = client.get(f"/api/v1/rights/{sid}/publish-check").json()
    assert check["publishable"] is False
    assert any("expired" in x for x in check["reasons"])


def test_demo_mode_blocks_even_approved(setup, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)
    client, _ = setup
    sid = _source(setup)
    client.post(f"/api/v1/rights/{sid}/review", json={})
    client.patch(f"/api/v1/rights/{sid}",
                 json={"status": "APPROVED", "reviewer": "ed"})
    check = client.get(f"/api/v1/rights/{sid}/publish-check").json()
    assert check["publishable"] is False
    assert any("demo mode" in x for x in check["reasons"])


def test_legacy_ingestion_basis_stays_publishable(setup):
    """S4 USER_OWNED rows keep working and can enter re-review."""
    client, factory = setup
    sid = _source(setup)
    db = factory()
    db.add(models.RightsRecord(source_id=sid, status="USER_OWNED",
                               basis="USER_OWNED"))
    db.commit()
    db.close()
    assert client.get(
        f"/api/v1/rights/{sid}/publish-check").json()["publishable"] is True
    r = client.patch(f"/api/v1/rights/{sid}",
                     json={"status": "REVIEW_REQUIRED"})
    assert r.status_code == 200


def test_episode_publish_check(setup):
    client, factory = setup
    ep = client.post("/api/v1/episodes", json={"title": "E"}).json()["id"]
    good = _source(setup, "good")
    bad = _source(setup, "bad")
    for sid, start in ((good, 0.0), (bad, 10.0)):
        db = factory()
        m = models.Moment(source_id=sid, start_time=start, end_time=start + 5,
                          transcript_excerpt="t", final_score=50.0,
                          status="APPROVED")
        db.add(m)
        db.flush()
        db.add(models.EpisodeSegment(
            episode_id=ep, moment_id=m.id, sequence=int(start),
            duration=5.0, transition_type="cut"))
        db.commit()
        db.close()
    client.post(f"/api/v1/rights/{good}/review", json={})
    client.patch(f"/api/v1/rights/{good}",
                 json={"status": "APPROVED", "reviewer": "ed"})
    body = client.get(f"/api/v1/episodes/{ep}/publish-check").json()
    assert body["publishable"] is False
    assert body["ready_to_publish"] is False
    assert [b["source_id"] for b in body["blocked"]] == [bad]
    assert client.get("/api/v1/episodes/999/publish-check").status_code == 404
