"""Cluster route tests — real MiniLM embeddings (cached in S6)."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.main import create_app

GAMING = [
    "Major game update announced today",
    "Developers reveal new game update",
    "Players react to the game update",
    "Streamer tests the new game update",
]
TECH = ["Sourdough bread baking masterclass"]


@pytest.fixture()
def setup():
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
    return TestClient(app), factory


def _seed(setup):
    client, factory = setup
    db = factory()
    now = datetime.now(timezone.utc)
    for i, title in enumerate(GAMING + TECH):
        row = models.Source(
            provider="youtube", external_id=f"ct{i}", url="", title=title,
            category="gaming" if i < 4 else "cooking",
            view_count=500_000 * (i + 1), like_count=5_000 * (i + 1),
            comment_count=500 * (i + 1))
        db.add(row)
        db.flush()
        db.add(models.SourceSnapshot(
            source_id=row.id, view_count=row.view_count // 2,
            like_count=row.like_count // 2,
            comment_count=row.comment_count // 2,
            taken_at=now - timedelta(hours=5)))
        db.add(models.SourceSnapshot(
            source_id=row.id, view_count=row.view_count,
            like_count=row.like_count, comment_count=row.comment_count,
            taken_at=now))
    db.commit()
    db.close()


def test_cluster_groups_gaming_topic(setup):
    client, _ = setup
    _seed(setup)
    r = client.post("/api/v1/trends/cluster", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["clusters"] == 1
    trend = body["trends"][0]
    assert trend["sources"] == 4
    assert trend["score"] > 60

    events = client.get("/api/v1/trend-events").json()
    assert len(events) == 1
    assert events[0]["sources"] == 4
    assert events[0]["combined_views"] == 500_000 * (1 + 2 + 3 + 4)
    assert events[0]["category"] == "gaming"

    # rerun updates the same trend (history preserved, no dupes)
    r2 = client.post("/api/v1/trends/cluster", json={})
    assert r2.json()["trends"][0]["created"] is False
    assert len(client.get("/api/v1/trend-events").json()) == 1

    # CLUSTER_TRENDS job recorded
    assert r2.json()["clusters"] == 1


def test_cluster_empty_db(setup):
    client, _ = setup
    r = client.post("/api/v1/trends/cluster", json={})
    assert r.status_code == 200
    assert r.json() == {"trends": [], "clusters": 0, "sources": 0}
