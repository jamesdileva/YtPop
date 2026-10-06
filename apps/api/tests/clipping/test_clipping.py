"""Golden + unit tests for clip detection (keyword path, no model)."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.domain.clipping import service as clipping

GOLDEN_SEGMENTS = [
    {"start": 0.0, "end": 4.0, "text": "Welcome back to the channel."},
    {"start": 4.0, "end": 10.0, "text": "Today I will show you something insane."},
    {"start": 10.0, "end": 16.0,
     "text": "How to beat the final boss in under one minute?"},
    {"start": 16.0, "end": 22.0,
     "text": "First, you need the secret sword upgrade."},
    {"start": 22.0, "end": 28.0,
     "text": "Wow, look at this damage, it is unbelievable!"},
    {"start": 28.0, "end": 34.0,
     "text": "And then it happened again last time."},
    {"start": 34.0, "end": 40.0,
     "text": "The winner gets the best reward chest."},
]
GOLDEN_TITLE = "How to beat the final boss"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _source_with_transcript(db, title=GOLDEN_TITLE, segments=GOLDEN_SEGMENTS):
    row = models.Source(provider="youtube", external_id="g1",
                        url="", title=title)
    db.add(row)
    db.flush()
    db.add(models.Transcript(
        source_id=row.id, language="en", model="test",
        text=" ".join(s["text"] for s in segments),
        segments_json=json.dumps(segments), audio_sha256="x",
    ))
    db.commit()
    return row.id


def test_golden_top_moment_matches_expected_range(db):
    """Known input + config = expected candidate range ±2s."""
    src_id = _source_with_transcript(db)
    summary = clipping.find_moments(
        db, src_id, top_k=10, use_embeddings=False,
    )
    assert summary["total"] > 0
    top = summary["top"][0]
    assert top["start"] == pytest.approx(10.0, abs=2.0)
    assert "boss" in top["text"]


def test_deterministic_rerun(db):
    src_id = _source_with_transcript(db)
    first = clipping.find_moments(db, src_id, use_embeddings=False)
    second = clipping.find_moments(db, src_id, use_embeddings=False)
    assert [t["start"] for t in first["top"]] == [
        t["start"] for t in second["top"]]
    assert [t["final_score"] for t in first["top"]] == [
        t["final_score"] for t in second["top"]]


def test_all_candidates_stored_not_deleted(db):
    src_id = _source_with_transcript(db)
    summary = clipping.find_moments(db, src_id, top_k=3, use_embeddings=False)
    assert summary["total"] > 3  # more candidates than top_k
    assert db.query(models.Moment).count() == summary["total"]


def test_weights_editable_without_code(db):
    src_id = _source_with_transcript(db)
    cfg = clipping.load_scoring()
    cfg["weights"]["hook"] = 0.0
    cfg["weights"]["relevance"] = 0.0
    plain = clipping.find_moments(
        db, src_id, weights_cfg=cfg, use_embeddings=False)
    default = clipping.find_moments(db, src_id, use_embeddings=False)
    assert plain["top"][0]["final_score"] < default["top"][0]["final_score"]


def test_scoring_yaml_loads():
    cfg = clipping.load_scoring()
    assert cfg["windows"]["min_duration"] == 5.0
    assert cfg["weights"]["hook"] == 20.0
    assert "wow" in cfg["emotion_words"]


def test_no_transcript_raises(db):
    row = models.Source(provider="youtube", external_id="bare", url="")
    db.add(row)
    db.commit()
    with pytest.raises(clipping.ClipError, match="no transcript"):
        clipping.find_moments(db, row.id, use_embeddings=False)


def test_missing_source_raises(db):
    with pytest.raises(clipping.ClipError, match="source not found"):
        clipping.find_moments(db, 999, use_embeddings=False)


def test_fake_embeddings_add_semantic_signal(db):
    def fake_embed(texts):
        # 2-D deterministic vectors from text length
        import math
        vecs = []
        for t in texts:
            v = [float(len(t) % 7 + 1), float(len(t.split()) % 5 + 1)]
            n = math.sqrt(v[0] ** 2 + v[1] ** 2)
            vecs.append([v[0] / n, v[1] / n])
        return vecs

    src_id = _source_with_transcript(db)
    summary = clipping.find_moments(db, src_id, embed_fn=fake_embed)
    rows = db.query(models.Moment).all()
    assert any(r.semantic_score > 0 for r in rows)
    assert len(summary["top"]) == min(10, summary["total"])
    # semantic path stays deterministic
    again = clipping.find_moments(db, src_id, embed_fn=fake_embed)
    assert [t["start"] for t in again["top"]] == [
        t["start"] for t in summary["top"]]
