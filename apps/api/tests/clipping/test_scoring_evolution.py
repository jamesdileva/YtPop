"""S14 scoring evolution: vision detector, ranker stub, LLM flag, export."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.domain.clipping import ranker
from app.domain.clipping import service as clipping
from app.domain.clipping import vision as vision_mod
from app.main import create_app
from app.services import ffmpeg_service as ff
from tests.clipping.test_clipping import GOLDEN_SEGMENTS, GOLDEN_TITLE


@pytest.fixture()
def db(tmp_path):
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _media(tmp_path, name="v.mp4", src="testsrc2=size=160x120:rate=10:duration=6"):
    out = tmp_path / name
    ff.run_cmd("ffmpeg", [
        "-y", "-f", "lavfi", "-i", src,
        "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(out)])
    return out


def test_motion_beats_static(tmp_path):
    moving = _media(tmp_path, "moving.mp4")
    static = _media(tmp_path, "static.mp4",
                    "color=c=0x1a1a2e:size=160x120:rate=10:duration=6")
    roots = [tmp_path]
    m_score = vision_mod.score_window_visual(moving, 0.0, 6.0, roots=roots)
    s_score = vision_mod.score_window_visual(static, 0.0, 6.0, roots=roots)
    assert m_score > s_score
    assert 0.0 <= s_score <= 1.0 and 0.0 <= m_score <= 1.0


def test_visual_interest_units():
    flat = [[128] * 100, [128] * 100]
    assert vision_mod.visual_interest(flat) < 0.5
    assert vision_mod.visual_interest([flat[0]]) == 0.0
    changing = [[0] * 100, [255] * 100]
    assert vision_mod.visual_interest(changing) > 0.5


def test_ranker_identity_and_bump():
    scored = [{"final_score": 10.0, "feats": {"emotion": 1.0}}]
    assert ranker.apply(scored, None)[0]["final_score"] == 10.0
    assert ranker.load_weights(None) is None
    assert ranker.load_weights("/nope/missing.json") is None
    bumped = ranker.apply(
        [{"final_score": 10.0, "feats": {"emotion": 1.0}}],
        {"features": ["emotion"], "coefficients": {"emotion": 5.0}})
    assert bumped[0]["final_score"] == 15.0


def _seed(db, tmp_path, title=GOLDEN_TITLE):
    media = _media(tmp_path)
    row = models.Source(provider="youtube", external_id="vis",
                        url="", title=title)
    db.add(row)
    db.flush()
    db.add(models.MediaAsset(source_id=row.id, kind="raw", path=str(media),
                             duration=6.0))
    db.add(models.Transcript(
        source_id=row.id, language="en", model="test", text="t",
        segments_json=json.dumps([
            {"start": 0.0, "end": 3.0, "text": "Wow, amazing start!"},
            {"start": 3.0, "end": 6.0, "text": "How to win it all?"}]),
        audio_sha256="x"))
    db.commit()
    return row.id


def test_vision_enabled_stores_scores(db, tmp_path):
    src_id = _seed(db, tmp_path)
    cfg = clipping.load_scoring()
    cfg["vision"]["enabled"] = True
    summary = clipping.find_moments(
        db, src_id, weights_cfg=cfg, use_embeddings=False,
        roots=[tmp_path])
    assert summary["total"] > 0
    visuals = [r.visual_score for r in db.query(models.Moment).all()]
    assert any(v > 0 for v in visuals)


def test_vision_off_by_default(db, tmp_path):
    src_id = _seed(db, tmp_path)
    clipping.find_moments(db, src_id, use_embeddings=False)
    assert {r.visual_score for r in db.query(models.Moment).all()} == {0.0}


def test_llm_flag_boosts_finalists(db, tmp_path):
    class FakeLLM:
        def chat_json(self, system, user):
            return {"scores": {"0": 1.0}}

    src_id = _seed(db, tmp_path)
    cfg = clipping.load_scoring()
    cfg["llm_scoring"]["enabled"] = True
    plain = clipping.find_moments(db, src_id, use_embeddings=False)
    boosted = clipping.find_moments(
        db, src_id, weights_cfg=cfg, use_embeddings=False, llm=FakeLLM())
    assert boosted["top"][0]["final_score"] > plain["top"][0]["final_score"]


def _client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool, future=True)
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


def test_feedback_export():
    client, factory = _client()
    src_id = client.post("/api/v1/sources", json={
        "external_id": "fb", "title": "F"}).json()["id"]
    db = factory()
    m = models.Moment(source_id=src_id, start_time=1.0, end_time=6.0,
                      transcript_excerpt="t", semantic_score=0.5,
                      final_score=40.0)
    db.add(m)
    db.flush()
    db.add(models.MomentFeedback(
        moment_id=m.id, decision="APPROVED", reason="hook",
        original_start=1.0, original_end=6.0,
        adjusted_start=1.5, adjusted_end=6.0))
    db.commit()
    db.close()
    body = client.get("/api/v1/feedback/export").json()
    assert body["count"] == 1
    row = body["rows"][0]
    assert (row["decision"], row["reason"]) == ("APPROVED", "hook")
    assert row["adjusted_start"] == 1.5 and row["final_score"] == 40.0
    csv_resp = client.get("/api/v1/feedback/export?format=csv")
    assert csv_resp.status_code == 200
    assert "decision" in csv_resp.text.splitlines()[0]
    assert "APPROVED" in csv_resp.text
    assert client.get("/api/v1/feedback/export?format=xml").status_code == 400
