"""Clustering + scoring unit tests — deterministic fake embeddings."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.domain.discovery import clustering


def fake_embed(texts):
    """A–D near-identical, everything else well separated (deterministic)."""
    import hashlib
    import math

    vecs = []
    for t in texts:
        low = t.lower()
        if "sourdough" in low:
            v = [0.0, 1.0, 0.0]
        elif "update" in low:
            v = [1.0, 0.05 * (len(t) % 3), 0.0]
        else:
            h = int(hashlib.md5(low.encode()).hexdigest(), 16)
            v = [0.0] * 8
            v[h % 8] = 1.0
            v[(h >> 3) % 8] += 0.5
        n = math.sqrt(sum(x * x for x in v))
        vecs.append([x / n for x in v])
    return vecs


TITLES = [
    "Major game update announced",
    "Developers reveal new update",
    "Players react to update",
    "Streamer tests update",
    "Sourdough bread baking guide",
]


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


def _seed(db, views=(100_000, 200_000, 300_000, 400_000, 5_000),
          hours_ago: float = 5.0):
    ids = []
    now = datetime.now(timezone.utc)
    for i, title in enumerate(TITLES):
        row = models.Source(provider="youtube", external_id=f"t{i}",
                            url="", title=title, category="gaming",
                            view_count=views[i], like_count=views[i] // 10,
                            comment_count=views[i] // 100)
        db.add(row)
        db.flush()
        db.add(models.SourceSnapshot(
            source_id=row.id, view_count=views[i] // 2,
            like_count=views[i] // 20, comment_count=views[i] // 200,
            taken_at=now - timedelta(hours=hours_ago)))
        db.add(models.SourceSnapshot(
            source_id=row.id, view_count=views[i],
            like_count=views[i] // 10, comment_count=views[i] // 100,
            taken_at=now))
        ids.append(row.id)
    db.commit()
    return ids


def test_abcd_forms_one_topic(db):
    _seed(db)
    out = clustering.cluster_trends(db, embed_fn=fake_embed)
    assert out["clusters"] == 1
    assert out["sources"] == 5
    trend = out["trends"][0]
    assert trend["sources"] == 4
    assert trend["created"] is True
    assert trend["score"] > 60
    assert set(trend) >= {"trend_id", "topic", "score", "velocity",
                          "components"}


def test_rerun_updates_instead_of_duplicating(db):
    _seed(db)
    first = clustering.cluster_trends(db, embed_fn=fake_embed)
    second = clustering.cluster_trends(db, embed_fn=fake_embed)
    assert second["trends"][0]["created"] is False
    assert second["trends"][0]["trend_id"] == first["trends"][0]["trend_id"]
    assert db.query(models.TrendEvent).count() == 1


def test_deterministic_scores(db):
    _seed(db)
    a = clustering.cluster_trends(db, embed_fn=fake_embed)
    # fresh DB, same seed → identical score
    db2_engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(db2_engine)
    maker = sessionmaker(bind=db2_engine, expire_on_commit=False)
    db2 = maker()
    _seed(db2)
    b = clustering.cluster_trends(db2, embed_fn=fake_embed)
    db2.close()
    assert a["trends"][0]["score"] == b["trends"][0]["score"]


def test_weights_editable(db):
    _seed(db)
    cfg = clustering.load_trend_config()
    cfg["weights"] = {"views_velocity": 1.0, "engagement_velocity": 0.0,
                      "recency": 0.0, "cross_source": 0.0, "momentum": 0.0,
                      "novelty": 0.0}
    out = clustering.cluster_trends(db, cfg=cfg, embed_fn=fake_embed)
    assert out["trends"][0]["components"]["views_velocity"] > 0
    with pytest.raises(clustering.TrendError, match="sum to 1.0"):
        bad = clustering.load_trend_config()
        bad["weights"]["views_velocity"] = 0.99
        clustering.cluster_trends(db, cfg=bad, embed_fn=fake_embed)


def test_config_loads():
    cfg = clustering.load_trend_config()
    assert cfg["similarity_threshold"] == 0.55
    assert abs(sum(cfg["weights"].values()) - 1.0) < 0.01


def test_singletons_ignored(db):
    now = datetime.now(timezone.utc)
    for i in range(3):
        row = models.Source(provider="youtube", external_id=f"s{i}",
                            url="", title=f"Totally unrelated thing {i} xyz")
        db.add(row)
        db.flush()
        for v in (100, 200):
            db.add(models.SourceSnapshot(
                source_id=row.id, view_count=v, like_count=1,
                comment_count=0, taken_at=now))
    db.commit()
    out = clustering.cluster_trends(db, embed_fn=fake_embed)
    assert out["clusters"] == 0
    assert db.query(models.TrendEvent).count() == 0


def test_fallback_topic_deterministic(db):
    _seed(db)
    members = db.query(models.Source).all()[:4]
    t1 = clustering.fallback_topic(members)
    t2 = clustering.fallback_topic(members)
    assert t1 == t2 and t1[0]
