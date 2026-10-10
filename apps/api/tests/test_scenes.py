"""D10 scene detection + clipping integration tests."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.domain.analysis import scenes
from app.domain.clipping import service as clipping
from app.services import ffmpeg_service
from app.services import scene_service

PARSED = """frame:0    pts:61440   pts_time:4
lavfi.scene_score=0.640000
frame:1    pts:122880  pts_time:8
lavfi.scene_score=1.000000
frame:2    pts:100     pts_time:0.3
lavfi.scene_score=0.050000
"""


def test_parse_scene_scores_pairs_and_orders():
    cuts = scene_service.parse_scene_scores(PARSED)
    assert cuts == [
        {"start": 0.3, "score": 0.05},
        {"start": 4.0, "score": 0.64},
        {"start": 8.0, "score": 1.0},
    ]


def test_parse_scene_scores_ignores_noise():
    assert scene_service.parse_scene_scores("garbage\nnot-a-score\n") == []
    # a score with no preceding frame line is dropped
    assert scene_service.parse_scene_scores(
        "lavfi.scene_score=0.9\n") == []


def test_detect_thresholds_and_caps(monkeypatch, tmp_path):
    media = tmp_path / "v.mp4"
    media.write_bytes(b"x")

    def fake_run_cmd(binary, args, timeout=300, cwd=None):
        assert binary == "ffmpeg"
        assert "select=scene,metadata=print:file=-" in args
        return PARSED

    monkeypatch.setattr(scene_service.ff, "run_cmd", fake_run_cmd)
    cuts = scene_service.detect_scenes(media, roots=[tmp_path],
                                       threshold=0.35, max_scenes=1)
    assert cuts == [{"start": 4.0, "score": 0.64}]  # capped at 1


def test_cuts_inside_and_snapping():
    assert clipping.cuts_inside([4.0, 8.0], 0.0, 10.0) == 2
    assert clipping.cuts_inside([4.0, 8.0], 4.0, 8.0) == 0  # not strict
    assert clipping.cuts_inside([], 0.0, 10.0) == 0
    snapped = clipping.snap_to_cuts(3.9, 8.05, [4.0, 8.0], 0.5)
    assert snapped == (4.0, 8.0)
    # too far away -> untouched
    assert clipping.snap_to_cuts(1.0, 12.0, [4.0, 8.0], 0.5) == (1.0, 12.0)


def test_apply_scene_scoring_penalises_and_snaps():
    scored = [
        {"start": 0.0, "end": 10.0, "final_score": 50.0},
        {"start": 4.5, "end": 8.5, "final_score": 50.0},
    ]
    clipping.apply_scene_scoring(scored, [5.0], penalty_weight=6.0)
    assert scored[0]["final_score"] == 44.0   # one cut inside
    assert scored[1]["final_score"] == 44.0   # also one cut inside

    scored2 = [{"start": 3.9, "end": 8.05, "final_score": 50.0}]
    clipping.apply_scene_scoring(scored2, [4.0, 8.0], penalty_weight=0.0,
                                snap=True, snap_tolerance=0.5)
    assert scored2[0]["start"] == 4.0
    assert scored2[0]["end"] == 8.0
    assert scored2[0]["final_score"] == 50.0  # penalty off


def test_no_cuts_is_a_no_op():
    scored = [{"start": 0.0, "end": 5.0, "final_score": 30.0}]
    clipping.apply_scene_scoring(scored, [], penalty_weight=6.0)
    assert scored[0]["final_score"] == 30.0


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


def test_detect_and_store_is_idempotent(db, monkeypatch, tmp_path):
    src = models.Source(provider="youtube", external_id="sc", url="",
                        title="Scene test")
    db.add(src)
    db.flush()
    media = tmp_path / "v.mp4"
    media.write_bytes(b"x")
    monkeypatch.setattr(scene_service.ff, "run_cmd",
                        lambda *a, **k: PARSED)
    out1 = scenes.detect_and_store(db, src.id, media, roots=[tmp_path])
    out2 = scenes.detect_and_store(db, src.id, media, roots=[tmp_path])
    assert out1["scenes"] == out2["scenes"] == 2
    assert db.query(models.Scene).count() == 2  # replaced, not appended
    assert scenes.get_scenes(db, src.id) == [4.0, 8.0]
    artifact = tmp_path / "scenes" / f"{src.id}.json"
    assert artifact.is_file()
    assert json.loads(artifact.read_text())["cuts"][0]["start"] == 4.0


def test_scenes_routes_commit_and_round_trip(db, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    from app.api.routes.scenes import router
    from app.db.database import get_db
    from app.main import create_app

    media = ffmpeg_service.repo_data_dir() / "raw" / "_test_scenes.mp4"
    media.parent.mkdir(parents=True, exist_ok=True)
    media.write_bytes(b"x")
    monkeypatch.setattr(scene_service.ff, "run_cmd",
                        lambda *a, **k: PARSED)
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool

    from app.api.routes.scenes import router
    from app.db.database import get_db
    from app.main import create_app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    src = models.Source(provider="youtube", external_id="rt", url="",
                        title="Route test")
    db.add(src)
    db.commit()

    app = create_app()
    app.include_router(router, prefix="/api/v1")

    def override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    r = client.post(f"/api/v1/sources/{src.id}/detect-scenes",
                    json={"media_path": "raw/_test_scenes.mp4"})
    assert r.status_code == 200, r.text
    assert r.json()["scenes"] == 2

    got = client.get(f"/api/v1/sources/{src.id}/scenes").json()
    assert [s["start_time"] for s in got["scenes"]] == [4.0, 8.0]
    assert client.post("/api/v1/sources/999/detect-scenes",
                      json={"media_path": "raw/_test_scenes.mp4"}).status_code == 404
    media.unlink(missing_ok=True)
    db.close()


def test_missing_source(db):
    with pytest.raises(scene_service.SceneError, match="source not found"):
        scenes.detect_and_store(db, 999, "x.mp4", roots=["."])


def test_find_moments_uses_stored_cuts(db):
    """A window straddling a hard cut must rank below a continuous one."""
    segments = [
        {"start": 0.0, "end": 5.0, "text": "Wow, amazing result!", "words": []},
        {"start": 5.0, "end": 10.0, "text": "How to win it all?", "words": []},
        {"start": 10.0, "end": 15.0, "text": "The final answer wins.",
         "words": []},
    ]
    src = models.Source(provider="youtube", external_id="sc2", url="",
                        title="Scene aware clip")
    db.add(src)
    db.flush()
    db.add(models.Transcript(
        source_id=src.id, language="en", model="test", text="t",
        segments_json=json.dumps(segments), audio_sha256="x"))
    # a hard cut at 7.5s splits the middle of the transcript
    db.add(models.Scene(source_id=src.id, index=0, start_time=7.5, score=0.9))
    db.commit()

    plain = clipping.find_moments(db, src.id, use_embeddings=False,
                                 cuts=[], weights_cfg=None)
    with_scenes = clipping.find_moments(db, src.id, use_embeddings=False,
                                       cuts=[7.5])
    assert with_scenes["top"][0]["final_score"] < \
        plain["top"][0]["final_score"]
