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
    """Known input + config = expected candidate range Â±2s."""
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
    # D1: top-k stays distinct coverage, never padded with near-copies
    assert 1 <= len(summary["top"]) <= min(10, summary["total"])
    picked = summary["top"]
    for i, a in enumerate(picked):
        for b in picked[i + 1:]:
            ratio = (min(a["end"], b["end"]) - max(a["start"], b["start"]))
            shorter = min(a["end"] - a["start"], b["end"] - b["start"])
            assert ratio / shorter <= 0.9
    # semantic path stays deterministic
    again = clipping.find_moments(db, src_id, embed_fn=fake_embed)
    assert [t["start"] for t in again["top"]] == [
        t["start"] for t in summary["top"]]

# --- D1 non-overlapping top-k --------------------------------------------------

def _win(start: float, end: float, score: float) -> dict:
    return {"start": start, "end": end, "final_score": score, "text": "x"}


def _windows_cfg(non_overlap: bool = True, max_overlap: float = 0.5) -> dict:
    return {"non_overlap": non_overlap, "max_overlap": max_overlap}


def test_select_top_suppresses_heavy_overlap():
    # A dominates; B/C/D all overlap A past 50% of the shorter window
    scored = [_win(5, 28, 82.0), _win(5, 31, 82.2), _win(5, 33, 81.8),
              _win(0, 28, 82.2), _win(24, 42, 67.8), _win(40, 60, 60.0)]
    order = clipping.select_top(scored, None, ["x"] * 6, 3,
                                clipping.load_scoring()["weights"],
                                windows=_windows_cfg())
    picked = [scored[i] for i in order]
    assert len(picked) == 3
    for i, a in enumerate(picked):
        for b in picked[i + 1:]:
            assert clipping._overlap_ratio(a, b) <= 0.5


def test_select_top_flag_off_keeps_overlaps():
    scored = [_win(5, 28, 82.0), _win(5, 31, 82.2), _win(24, 42, 67.8),
              _win(45, 60, 60.0)]
    weights = clipping.load_scoring()["weights"]
    off = clipping.select_top(scored, None, ["x"] * 4, 3, weights,
                              windows=_windows_cfg(non_overlap=False))
    on = clipping.select_top(scored, None, ["x"] * 4, 3, weights,
                             windows=_windows_cfg())
    # flag off: top-2 both start at 5s (duplicate coverage)
    assert scored[off[0]]["start"] == 5 and scored[off[1]]["start"] == 5
    # flag on: pairwise overlap stays under the threshold
    for i, a in enumerate(on):
        for b in on[i + 1:]:
            assert clipping._overlap_ratio(scored[a], scored[b]) <= 0.5
    assert on != off


def test_select_top_never_returns_near_duplicates():
    """Short clip where everything overlaps: return as many distinct
    candidates as fit, never padded with near-copies of the same coverage."""
    scored = [_win(0, 20, 90.0), _win(5, 25, 80.0), _win(10, 30, 70.0)]
    order = clipping.select_top(scored, None, ["x"] * 3, 3,
                                clipping.load_scoring()["weights"],
                                windows=_windows_cfg(max_overlap=0.05))
    assert 1 <= len(order) <= 3
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            assert clipping._overlap_ratio(
                scored[a], scored[b]) <= 0.9


def test_select_top_partial_relaxation_keeps_near_dupes_out():
    scored = [_win(0, 10, 90.0), _win(9, 20, 80.0), _win(19, 30, 70.0),
              _win(28, 38, 60.0)]
    order = clipping.select_top(scored, None, ["x"] * 4, 4,
                                clipping.load_scoring()["weights"],
                                windows=_windows_cfg(max_overlap=0.9))
    # 9-20 vs 0-10 overlaps 0.1 of the shorter window (1s/10s) -> allowed
    assert len(order) == 4
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            assert clipping._overlap_ratio(
                scored[a], scored[b]) <= 0.9


def test_find_moments_top_has_no_duplicate_time_windows(db):
    """End-to-end: top-k windows stay distinct when the clip allows it."""
    segments = [
        {"start": float(i * 4), "end": float(i * 4 + 4),
         "text": "Wow, look at this amazing result!", "words": []}
        for i in range(12)
    ]
    src_id = _source_with_transcript(db, segments=segments)
    summary = clipping.find_moments(db, src_id, top_k=5, use_embeddings=False)
    windows = summary["top"]
    assert len(windows) == 5
    for i, a in enumerate(windows):
        for b in windows[i + 1:]:
            ratio = (min(a["end"], b["end"]) - max(a["start"], b["start"]))
            shorter = min(a["end"] - a["start"], b["end"] - b["start"])
            assert ratio / shorter <= 0.5


def test_all_candidates_still_available(db):
    src_id = _source_with_transcript(db)
    summary = clipping.find_moments(db, src_id, top_k=3, use_embeddings=False)
    assert db.query(models.Moment).count() == summary["total"]
