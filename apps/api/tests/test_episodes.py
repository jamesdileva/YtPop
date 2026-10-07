"""S8 episode builder tests: 5-clip build, reorder, duration, cards."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.main import create_app


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


def _approved_moment(client, factory, idx, start, end) -> int:
    src_id = client.post("/api/v1/sources", json={
        "external_id": f"s8-{idx}", "title": "S8",
    }).json()["id"]
    db = factory()
    m = models.Moment(source_id=src_id, start_time=start, end_time=end,
                      transcript_excerpt=f"clip {idx}", final_score=90.0 - idx,
                      status="APPROVED")
    db.add(m)
    db.commit()
    mid = m.id
    db.close()
    return mid


def test_create_applies_template(setup):
    client, _ = setup
    r = client.post("/api/v1/episodes", json={"template": "daily_highlights"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["target_duration"] == 20 * 60
    assert [s["kind"] for s in body["segments"]] == ["card", "card"]
    assert body["actual_duration"] == 4.0 + 5.0
    assert body["over_under"] == 9.0 - 1200.0


def test_five_clip_build_reorder_reload(setup):
    client, factory = setup
    ep = client.post("/api/v1/episodes", json={"title": "Ep"}).json()["id"]
    mids = [_approved_moment(client, factory, i, i * 10.0, i * 10.0 + 8.0)
            for i in range(5)]
    for mid in mids:
        r = client.post(f"/api/v1/episodes/{ep}/segments",
                        json={"moment_id": mid})
        assert r.status_code == 200, r.text
    body = client.get(f"/api/v1/episodes/{ep}").json()
    clips = [s for s in body["segments"] if s["kind"] == "clip"]
    assert len(clips) == 5
    assert [s["moment_id"] for s in clips] == mids
    assert body["actual_duration"] == 9.0 + 5 * 8.0  # cards + clips

    # reorder: reverse the clips, keep cards where they are
    cards = [s["id"] for s in body["segments"] if s["kind"] == "card"]
    rev = [s["id"] for s in reversed(clips)]
    order = [cards[0], *rev, cards[1]]
    r = client.post(f"/api/v1/episodes/{ep}/rebuild",
                    json={"segment_ids": order})
    assert r.status_code == 200, r.text
    reloaded = client.get(f"/api/v1/episodes/{ep}").json()
    assert [s["id"] for s in reloaded["segments"]] == order
    assert any(
        s["moment_id"] == mids[0]
        for s in reloaded["segments"][-3:]
    )


def test_rebuild_rejects_wrong_set(setup):
    client, _ = setup
    ep = client.post("/api/v1/episodes", json={}).json()["id"]
    assert client.post(f"/api/v1/episodes/{ep}/rebuild",
                       json={"segment_ids": [999]}).status_code == 400


def test_unapproved_moment_blocked(setup):
    client, factory = setup
    ep = client.post("/api/v1/episodes", json={}).json()["id"]
    src_id = client.post("/api/v1/sources", json={
        "external_id": "raw", "title": "x"}).json()["id"]
    db = factory()
    m = models.Moment(source_id=src_id, start_time=0, end_time=5,
                      transcript_excerpt="t", final_score=1.0,
                      status="CANDIDATE")
    db.add(m)
    db.commit()
    mid = m.id
    db.close()
    assert client.post(f"/api/v1/episodes/{ep}/segments",
                       json={"moment_id": mid}).status_code == 400


def test_trim_duplicate_delete(setup):
    client, factory = setup
    ep = client.post("/api/v1/episodes", json={}).json()["id"]
    mid = _approved_moment(client, factory, 0, 0.0, 10.0)
    body = client.post(f"/api/v1/episodes/{ep}/segments",
                       json={"moment_id": mid}).json()
    seg = [s for s in body["segments"] if s["kind"] == "clip"][0]

    trimmed = client.patch(
        f"/api/v1/episodes/{ep}/segments/{seg['id']}",
        json={"duration": 6.0}).json()
    assert trimmed["actual_duration"] == 9.0 + 6.0

    duped = client.post(
        f"/api/v1/episodes/{ep}/segments/{seg['id']}/duplicate").json()
    clips = [s for s in duped["segments"] if s["kind"] == "clip"]
    assert len(clips) == 2
    assert clips[0]["moment_id"] == clips[1]["moment_id"] == mid
    assert duped["actual_duration"] == 9.0 + 12.0

    after = client.delete(
        f"/api/v1/episodes/{ep}/segments/{clips[0]['id']}").json()
    assert [s["sequence"] for s in after["segments"]] == list(
        range(len(after["segments"])))
    assert after["actual_duration"] == 9.0 + 6.0


def test_episode_patch_and_404s(setup):
    client, _ = setup
    ep = client.post("/api/v1/episodes", json={}).json()["id"]
    r = client.patch(f"/api/v1/episodes/{ep}",
                     json={"title": "New", "target_duration": 60.0})
    assert r.json()["title"] == "New"
    assert r.json()["over_under"] == 9.0 - 60.0
    assert client.get("/api/v1/episodes/999").status_code == 404
    assert client.post("/api/v1/episodes/999/segments",
                       json={"duration": 3.0}).status_code == 404
