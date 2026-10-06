"""Domain tests — upsert/snapshots/velocity/score/sections/quota (no network)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.domain.discovery import service as discovery


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


def _item(vid: str = "v1", views: int = 1000, cat: str = "gaming") -> dict:
    return {
        "provider": "youtube", "external_id": vid,
        "url": f"https://www.youtube.com/watch?v={vid}",
        "title": f"Title {vid}", "channel_id": "ch",
        "channel_name": "Ch", "category": cat,
        "view_count": views, "like_count": 10, "comment_count": 2,
    }


def test_upsert_creates_source_and_snapshot(db):
    row, created = discovery.upsert_source(db, _item())
    assert created is True
    assert row.trend_score > 0
    assert db.query(models.SourceSnapshot).count() == 1


def test_upsert_updates_and_adds_snapshot(db):
    row, _ = discovery.upsert_source(db, _item(views=1000))
    _, created2 = discovery.upsert_source(db, _item(views=3000))
    assert created2 is False
    assert db.query(models.SourceSnapshot).count() == 2
    assert db.get(models.Source, row.id).view_count == 3000


def test_velocity_needs_two_snapshots(db):
    row, _ = discovery.upsert_source(db, _item())
    assert discovery.compute_velocity(db, row.id) == 0.0


def test_velocity_math(db):
    row, _ = discovery.upsert_source(db, _item(views=1000))
    snap = db.query(models.SourceSnapshot).one()
    snap.taken_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db.flush()
    discovery.upsert_source(db, _item(views=3000))
    assert discovery.compute_velocity(db, row.id) == pytest.approx(1000.0)


def test_trend_score_deterministic():
    a = discovery.compute_trend_score(1000, 10, 2, 500.0)
    b = discovery.compute_trend_score(1000, 10, 2, 500.0)
    assert a == b
    assert discovery.compute_trend_score(2000, 10, 2, 0.0) > discovery.compute_trend_score(
        1000, 10, 2, 0.0
    )


def test_trending_sections_keys_and_order(db):
    discovery.upsert_source(db, _item("big", views=50000, cat="gaming"))
    discovery.upsert_source(db, _item("small", views=100, cat="tech"))
    sections = discovery.trending_sections(db)
    assert set(sections) == {
        "trending_now", "recently_rising", "fastest_growing", "top_categories",
    }
    assert sections["trending_now"][0]["external_id"] == "big"
    assert {c["category"] for c in sections["top_categories"]} == {"gaming", "tech"}


def test_quota_guard_blocks(db):
    discovery.record_run(db, "search", "US", "", 100, 5)
    with pytest.raises(discovery.QuotaExceeded):
        discovery.check_quota(db, 1, daily_budget=100)
    # within budget passes
    discovery.check_quota(db, 1, daily_budget=101)
    assert discovery.quota_used_today(db) == 100
