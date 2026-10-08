"""D4 tests: dataset building, logistic fit, weights round-trip, apply()."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.domain.clipping import ranker
from app.domain.clipping import training


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


def _moment_with_feats(db, feats: dict, ext: str) -> int:
    src = models.Source(provider="youtube", external_id=ext, url="")
    db.add(src)
    db.flush()
    m = models.Moment(source_id=src.id, start_time=0.0, end_time=8.0,
                      transcript_excerpt="t", final_score=50.0,
                      features_json=json.dumps(feats))
    db.add(m)
    db.flush()
    return m.id


def _feedback(db, moment_id: int, decision: str) -> None:
    db.add(models.MomentFeedback(
        moment_id=moment_id, decision=decision, reason="test",
        original_start=0.0, original_end=8.0,
        adjusted_start=0.0, adjusted_end=8.0))
    db.flush()


def test_logistic_recovers_separable_signal():
    # label 1 when f1 is high, label 0 when f1 is low
    rows = [[10.0, 0.0], [12.0, 1.0], [14.0, 0.0], [11.0, 2.0],
            [0.0, 1.0], [1.0, 0.0], [2.0, 2.0], [0.5, 1.0]]
    labels = [1, 1, 1, 1, 0, 0, 0, 0]
    coef, bias, means, stds = training.train_logistic(rows, labels)
    # f1 (first feature) must carry the positive weight
    assert coef[0] > 0.5
    assert len(means) == 2 and len(stds) == 2
    # deterministic: same inputs -> identical outputs
    coef2, bias2, _, _ = training.train_logistic(rows, labels)
    assert coef == coef2 and bias == bias2


def test_dataset_maps_decisions_and_skips_ambiguous(db):
    ids = []
    for i in range(6):
        feats = {"hook": 1.0 if i < 3 else 0.0, "emotion": float(i)}
        ids.append(_moment_with_feats(db, feats, f"dd{i}"))
    _feedback(db, ids[0], "APPROVED")
    _feedback(db, ids[1], "APPROVED")
    _feedback(db, ids[2], "USER_OWNED")
    _feedback(db, ids[3], "REJECTED")
    _feedback(db, ids[4], "REJECTED")
    _feedback(db, ids[5], "TRIMMED")  # ambiguous -> skipped
    db.commit()
    rows, labels, decisions = training.build_dataset(db)
    assert len(rows) == 5 and sum(labels) == 3
    assert "TRIMMED" in decisions


def test_dataset_ignores_moments_without_features(db):
    src = models.Source(provider="youtube", external_id="nofeat", url="")
    db.add(src)
    db.flush()
    m = models.Moment(source_id=src.id, start_time=0.0, end_time=5.0,
                      transcript_excerpt="t", features_json="")
    db.add(m)
    db.flush()
    _feedback(db, m.id, "APPROVED")
    db.commit()
    rows, labels, _ = training.build_dataset(db)
    assert rows == [] and labels == []


def test_train_refuses_thin_or_single_class_data(db):
    # too few labelled rows
    for i in range(3):
        mid = _moment_with_feats(db, {"hook": 1.0}, f"thin{i}")
        _feedback(db, mid, "APPROVED")
    db.commit()
    with pytest.raises(training.TrainingError, match="at least 10"):
        training.train(db, min_rows=10)

    # enough rows but only one class
    for i in range(3, 15):
        mid = _moment_with_feats(db, {"hook": 1.0}, f"same{i}")
        _feedback(db, mid, "APPROVED")
    db.commit()
    with pytest.raises(training.TrainingError, match="both approved"):
        training.train(db, min_rows=10)


def test_weights_round_trip_and_apply(db, tmp_path):
    rows = [{"hook": 10.0 if i % 2 == 0 else 0.0, "emotion": 0.0}
            for i in range(12)]
    labels = [1 if i % 2 == 0 else 0 for i in range(12)]
    coef, bias, means, stds = training.train_logistic(
        [[r["hook"], r["emotion"]] for r in rows], labels)
    names = ["hook", "emotion"]
    weights = {
        "version": 1, "features": names,
        "coefficients": dict(zip(names, coef)),
        "bias": bias,
        "mean": dict(zip(names, means)), "std": dict(zip(names, stds)),
    }
    path = training.write_weights(weights, tmp_path / "ranker.json")
    loaded = ranker.load_weights(path)
    assert loaded is not None
    assert loaded["features"] == names

    # a high-hook candidate must rank above a low-hook one after apply()
    scored = [
        {"final_score": 50.0, "feats": {"hook": 10.0, "emotion": 0.0}},
        {"final_score": 50.0, "feats": {"hook": 0.0, "emotion": 0.0}},
    ]
    out = ranker.apply(scored, loaded)
    assert out[0]["final_score"] > out[1]["final_score"]
    assert out[0]["final_score"] != 50.0  # actually applied, not passthrough
    # without weights: untouched
    untouched = [{"final_score": 50.0, "feats": {"hook": 10.0, "emotion": 0.0}}]
    assert ranker.apply(untouched, None)[0]["final_score"] == 50.0


def test_missing_weights_file_is_ignored(tmp_path):
    assert ranker.load_weights(tmp_path / "nope.json") is None
    assert ranker.load_weights(None) is None
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    assert ranker.load_weights(bad) is None


def test_find_moments_persists_features(db):
    from app.domain.clipping import service as clipping

    segments = [
        {"start": 0.0, "end": 6.0, "text": "Wow, amazing start!", "words": []},
        {"start": 6.0, "end": 12.0, "text": "How to win it all?", "words": []},
        {"start": 12.0, "end": 18.0, "text": "The final answer wins.",
         "words": []},
    ]
    src = models.Source(provider="youtube", external_id="feats", url="",
                        title="Feature persistence")
    db.add(src)
    db.flush()
    db.add(models.Transcript(
        source_id=src.id, language="en", model="test", text="t",
        segments_json=json.dumps(segments), audio_sha256="x"))
    db.commit()
    clipping.find_moments(db, src.id, use_embeddings=False)
    saved = db.query(models.Moment).all()
    assert saved
    feats = json.loads(saved[0].features_json)
    for key in ("hook", "relevance", "novelty", "emotion", "payoff",
                "completeness", "dead_air", "context_dependency",
                "duration", "wps"):
        assert key in feats, f"missing persisted feature {key}"
