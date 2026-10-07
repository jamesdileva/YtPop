"""S7 review tests: PATCH decisions + feedback, previews, filters, CORS."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.moments import get_embedder
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.main import create_app
from app.services import ffmpeg_service as ff


@pytest.fixture()
def setup(tmp_path):
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
    app.dependency_overrides[get_embedder] = lambda: None
    return TestClient(app), factory, tmp_path


def _moment(setup, status="CANDIDATE", start=5.0, end=15.0,
            media: Path | None = None) -> int:
    client, factory, tmp_path = setup
    src_id = client.post("/api/v1/sources", json={
        "external_id": f"s7-{start}", "title": "S7",
    }).json()["id"]
    if media is None:
        media = tmp_path / "src.mp4"
        if not media.is_file():
            ff.run_cmd("ffmpeg", [
                "-y", "-f", "lavfi", "-i",
                "testsrc2=size=160x120:rate=10:duration=30",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-shortest", str(media),
            ])
    db = factory()
    db.add(models.MediaAsset(source_id=src_id, kind="raw", path=str(media),
                             duration=30.0, codec="h264"))
    m = models.Moment(source_id=src_id, start_time=start, end_time=end,
                      transcript_excerpt="t", final_score=42.0, status=status)
    db.add(m)
    db.commit()
    mid = m.id
    db.close()
    return mid


def _clips_dir() -> Path:
    from app.services.ffmpeg_service import repo_data_dir

    return repo_data_dir() / "clips"


def test_approve_writes_feedback(setup):
    client, factory, _ = setup
    mid = _moment(setup)
    r = client.patch(f"/api/v1/moments/{mid}",
                     json={"status": "APPROVED", "reason": "strong hook"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"
    db = factory()
    fb = db.query(models.MomentFeedback).one()
    assert (fb.decision, fb.reason) == ("APPROVED", "strong hook")
    assert (fb.original_start, fb.adjusted_start) == (5.0, 5.0)
    db.close()


def test_trim_updates_times_and_feedback(setup):
    client, factory, _ = setup
    mid = _moment(setup)
    r = client.patch(f"/api/v1/moments/{mid}",
                     json={"start_time": 6.0, "end_time": 12.0,
                           "notes": "tighter", "category": "funny",
                           "is_best": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["start_time"], body["end_time"]) == (6.0, 12.0)
    assert body["notes"] == "tighter" and body["is_best"] is True
    db = factory()
    fb = db.query(models.MomentFeedback).one()
    assert fb.decision == "TRIMMED"
    assert (fb.original_start, fb.original_end) == (5.0, 15.0)
    assert (fb.adjusted_start, fb.adjusted_end) == (6.0, 12.0)
    db.close()


def test_patch_rejects_bad_input(setup):
    client, _, _ = setup
    mid = _moment(setup)
    assert client.patch(f"/api/v1/moments/{mid}",
                        json={"status": "AI_CONFIRMED"}).status_code == 400
    assert client.patch(f"/api/v1/moments/{mid}",
                        json={"start_time": 20.0,
                              "end_time": 10.0}).status_code == 400
    assert client.patch("/api/v1/moments/999",
                        json={"status": "APPROVED"}).status_code == 404


def test_preview_build_and_serve(setup):
    client, _, _ = setup
    mid = _moment(setup)
    try:
        r = client.post(f"/api/v1/moments/{mid}/preview")
        assert r.status_code == 200, r.text
        assert r.json()["cached"] is False
        clip = _clips_dir() / f"{mid}.mp4"
        assert clip.is_file() and clip.stat().st_size > 0
        info = ff.probe(clip, [clip.parent.parent])
        assert info["duration"] == 10.0

        g = client.get(f"/api/v1/moments/{mid}/preview")
        assert g.status_code == 200
        assert g.headers["content-type"] == "video/mp4"
        assert client.get("/api/v1/moments/999/preview").status_code == 404
    finally:
        for p in _clips_dir().glob(f"{mid}.mp4"):
            p.unlink(missing_ok=True)


def test_preview_without_media_is_400(setup):
    client, factory, tmp_path = setup
    src_id = client.post("/api/v1/sources", json={
        "external_id": "nomedia", "title": "x",
    }).json()["id"]
    db = factory()
    m = models.Moment(source_id=src_id, start_time=1.0, end_time=6.0,
                      transcript_excerpt="t", final_score=1.0)
    db.add(m)
    db.commit()
    mid = m.id
    db.close()
    assert client.post(f"/api/v1/moments/{mid}/preview").status_code == 400


def test_moments_filters(setup):
    client, _, _ = setup
    a = _moment(setup, status="APPROVED", start=1.0)
    _moment(setup, status="REJECTED", start=2.0)
    r = client.get("/api/v1/moments?status=APPROVED")
    assert r.status_code == 200
    ids = [m["id"] for m in r.json()]
    assert a in ids and len(ids) == 1
    r2 = client.get("/api/v1/moments?min_score=1000")
    assert r2.json() == []


def test_cors_allows_local_frontend(setup):
    client, _, _ = setup
    r = client.options(
        "/api/v1/moments",
        headers={"Origin": "http://localhost:5173",
                 "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == \
        "http://localhost:5173"
