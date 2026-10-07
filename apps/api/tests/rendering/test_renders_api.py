"""Render route tests: render flow, file serving, cancel, retry."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.main import create_app
from tests.rendering.fixtures import gen_clip


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
    client = TestClient(app)
    return client, factory, tmp_path


def _episode(client, factory, tmp_path, with_media: bool = True) -> int:
    ep_id = client.post("/api/v1/episodes", json={"title": "R"}).json()["id"]
    db = factory()
    for i in range(2):
        src = models.Source(provider="youtube", external_id=f"rr{i}", url="")
        db.add(src)
        db.flush()
        if with_media:
            media = gen_clip(tmp_path / f"rr{i}.mp4", 4)
            db.add(models.MediaAsset(source_id=src.id, kind="raw",
                                     path=str(media), duration=4.0))
        m = models.Moment(source_id=src.id, start_time=0.0, end_time=4.0,
                          transcript_excerpt="t", final_score=50.0,
                          status="APPROVED")
        db.add(m)
        db.flush()
        db.add(models.EpisodeSegment(
            episode_id=ep_id, moment_id=m.id, sequence=10 + i, duration=4.0,
            transition_type="cut"))
    db.commit()
    db.close()
    return ep_id


def _clean_renders():
    from pathlib import Path

    from app.services.ffmpeg_service import repo_data_dir

    data = repo_data_dir()
    for p in list((data / "renders").glob("*.mp4")):
        p.unlink(missing_ok=True)
    for p in list((data / "captions").glob("render_*.ass")):
        p.unlink(missing_ok=True)


def test_render_endpoint_flow(setup):
    client, factory, tmp_path = setup
    ep_id = _episode(client, factory, tmp_path)
    try:
        r = client.post(f"/api/v1/episodes/{ep_id}/render",
                        json={"preset": "preview_720p"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["qa"]["ok"], body["qa"]["failed"]
        rid = body["render_id"]

        g = client.get(f"/api/v1/renders/{rid}")
        assert g.status_code == 200
        assert g.json()["status"] == "COMPLETED"
        assert g.json()["qa"]["checks"]["resolution"] is True

        f = client.get(f"/api/v1/renders/{rid}/file")
        assert f.status_code == 200
        assert f.headers["content-type"] == "video/mp4"
        assert len(f.content) > 0

        listed = client.get(f"/api/v1/episodes/{ep_id}/renders").json()
        assert [x["id"] for x in listed] == [rid]

        c = client.post(f"/api/v1/renders/{rid}/cancel")
        assert c.status_code == 409
    finally:
        _clean_renders()


def test_failed_render_recorded_and_retryable(setup):
    client, factory, tmp_path = setup
    ep_id = _episode(client, factory, tmp_path, with_media=False)
    try:
        r = client.post(f"/api/v1/episodes/{ep_id}/render",
                        json={"preset": "preview_720p"})
        assert r.status_code == 400, r.text
        db = factory()
        failed = db.query(models.Render).filter_by(episode_id=ep_id).one()
        assert failed.status == "FAILED" and failed.error
        db.close()

        # retry after fixing media → new COMPLETED render
        db = factory()
        for seg in db.query(models.EpisodeSegment).filter_by(
                episode_id=ep_id).all():
            if seg.moment_id is not None:
                m = db.get(models.Moment, seg.moment_id)
                media = gen_clip(
                    tmp_path / f"fix{m.id}.mp4", 4)
                db.add(models.MediaAsset(source_id=m.source_id, kind="raw",
                                         path=str(media), duration=4.0))
        db.commit()
        db.close()
        r2 = client.post(f"/api/v1/episodes/{ep_id}/render",
                         json={"preset": "preview_720p"})
        assert r2.status_code == 200, r2.text
        assert r2.json()["qa"]["ok"]
    finally:
        _clean_renders()


def test_render_404s_and_bad_preset(setup):
    client, factory, tmp_path = setup
    assert client.post("/api/v1/episodes/999/render",
                       json={}).status_code == 404
    ep_id = _episode(client, factory, tmp_path)
    try:
        assert client.post(f"/api/v1/episodes/{ep_id}/render",
                           json={"preset": "nope"}).status_code == 400
        assert client.get("/api/v1/renders/999").status_code == 404
        assert client.get("/api/v1/renders/999/file").status_code == 404
        assert client.post("/api/v1/renders/999/cancel").status_code == 404
        assert client.get("/api/v1/episodes/999/renders").status_code == 404
    finally:
        _clean_renders()
