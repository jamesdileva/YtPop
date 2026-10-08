"""S13 orchestrator test: fake LLM + real ffmpeg, outputs under tmp."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.services import ffmpeg_service as ff
from app.workers import handlers, orchestrator
from app.workers import queue as q


class FakeEditorial:
    def plan(self, *, trend="", sources=None, moments=None,
             target_duration=1200.0, format="daily_highlights"):
        order = [m.id for m in (moments or [])]
        from app.domain.editorial.service import EpisodePlan

        return EpisodePlan.model_validate({
            "title": f"Daily — {trend or 'Test'}",
            "opening_hook": "Watch this",
            "hook_moment_id": order[0] if order else None,
            "story_clusters": [{"name": "All", "moment_ids": order,
                                "rationale": "test"}],
            "segment_order": order,
            "transitions": [], "context_requirements": [],
            "ending": "That is all", "titles": ["T"], "description": "",
        }), {"repairs": 0}


def _vectors(texts):
    import math

    out = []
    for t in texts:
        v = [1.0, 0.01 * len(t)] if "update" in t.lower() else [0.0, 1.0]
        n = math.sqrt(sum(x * x for x in v))
        out.append([x / n for x in v])
    return out


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


def _seed(db, tmp_path):
    for i, title in enumerate(["Major game update one",
                               "Major game update two"]):
        media = tmp_path / f"p{i}.mp4"
        ff.run_cmd("ffmpeg", [
            "-y", "-f", "lavfi", "-i",
            "testsrc2=size=320x240:rate=15:duration=4",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(media)])
        src = models.Source(provider="youtube", external_id=f"pp{i}",
                            url="", title=title, category="gaming",
                            view_count=2_000_000, like_count=20_000,
                            comment_count=2_000)
        db.add(src)
        db.flush()
        db.add(models.MediaAsset(source_id=src.id, kind="raw",
                                 path=str(media), duration=4.0))
        words = [{"start": 0.0, "end": 4.0, "word": " hello",
                  "probability": 0.99}]
        db.add(models.Transcript(
            source_id=src.id, language="en", model="test",
            text="hello", audio_sha256="x",
            segments_json=json.dumps([{"start": 0.0, "end": 4.0,
                                       "text": "hello", "words": words}])))
        db.add(models.Moment(
            source_id=src.id, start_time=0.0, end_time=4.0,
            transcript_excerpt="hello", final_score=80.0, status="APPROVED"))
    db.commit()


def test_daily_episode_end_to_end(db, tmp_path, monkeypatch):
    import app.domain.discovery.clustering as clustering_mod

    _seed(db, tmp_path)
    real_cluster = clustering_mod.cluster_trends
    monkeypatch.setattr(
        clustering_mod, "cluster_trends",
        lambda db_, **kw: real_cluster(db_, embed_fn=_vectors, **kw))
    ctx = handlers.Ctx(editorial=FakeEditorial(), roots=[tmp_path])
    out = orchestrator.run_daily_episode(db, ctx)
    assert out["episode_id"] > 0
    assert out["render_id"] > 0
    assert [s["status"] for s in out["stages"]] == ["COMPLETED"] * len(
        out["stages"])
    stage_names = [s["stage"] for s in out["stages"]]
    assert stage_names[:2] == ["refresh_scores", "cluster"]
    assert "generate" in stage_names and "render" in stage_names
    ep = db.get(models.Episode, out["episode_id"])
    clips = (db.query(models.EpisodeSegment)
             .filter_by(episode_id=ep.id)
             .filter(models.EpisodeSegment.moment_id.is_not(None)).all())
    assert len(clips) == 2
    render = db.get(models.Render, out["render_id"])
    assert render.status == "COMPLETED"
    assert all(j.status == "COMPLETED"
               for j in db.query(models.Job).all())


class FakeWhisper:
    model_name = "fake"

    def transcribe(self, wav_path, language=None, word_timestamps=True):
        return {
            "language": "en",
            "segments": [{"start": 0.0, "end": 6.0, "text": "caption test",
                          "confidence": -0.1,
                          "words": [{"start": 0.0, "end": 6.0,
                                     "word": " test", "probability": 1.0}]}],
            "text": "caption test",
        }


def test_transcribe_and_moments_jobs(db, tmp_path):
    media = tmp_path / "raw.mp4"
    ff.run_cmd("ffmpeg", [
        "-y", "-f", "lavfi", "-i",
        "testsrc2=size=320x240:rate=15:duration=4",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(media)])
    src = models.Source(provider="youtube", external_id="tj", url="",
                        title="Update news today")
    db.add(src)
    db.flush()
    db.add(models.MediaAsset(source_id=src.id, kind="raw", path=str(media),
                             duration=4.0))
    db.commit()
    ctx = handlers.Ctx(whisper=FakeWhisper(), embed_fn=_vectors,
                       roots=[tmp_path])
    t = q.enqueue(db, "TRANSCRIBE", {"source_id": src.id})
    db.commit()
    assert handlers.run_job(db, t.id, ctx)["segments"] == 1
    f = q.enqueue(db, "FIND_MOMENTS", {"source_id": src.id, "top_k": 5})
    db.commit()
    summary = handlers.run_job(db, f.id, ctx)
    assert summary["total"] >= 1
    assert db.query(models.Moment).count() == summary["total"]


def test_pipeline_aborts_without_approved(db, tmp_path):
    _seed(db, tmp_path)
    for m in db.query(models.Moment).all():
        m.status = "REJECTED"
    db.commit()
    ctx = handlers.Ctx(editorial=FakeEditorial(), roots=[tmp_path])
    with pytest.raises(orchestrator.PipelineError, match="no APPROVED"):
        orchestrator.run_daily_episode(db, ctx)
    failed_stages = [j for j in db.query(models.Job).all()
                     if j.status == "FAILED"]
    assert failed_stages == []
