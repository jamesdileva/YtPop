"""Route tests — Fake YouTubeService via dependency override (no network)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.trends import get_youtube_service
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.main import create_app


class FakeYT:
    def get_most_popular(self, region="US", category_id="", max_results=25):
        items = [
            {
                "provider": "youtube", "external_id": f"vid{i}",
                "url": f"https://www.youtube.com/watch?v=vid{i}",
                "title": f"Vid {i}", "channel_id": "ch",
                "channel_name": "Ch", "category": "gaming",
                "view_count": 1000 * (i + 1), "like_count": 5,
                "comment_count": 1,
            }
            for i in range(3)
        ]
        return items, 1


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
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
    app.dependency_overrides[get_youtube_service] = lambda: FakeYT()
    return TestClient(app)


def test_discover_persists_and_reports_quota(client):
    r = client.post(
        "/api/v1/sources/discover",
        json={"region": "US", "category": "", "max_results": 3},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"imported": 3, "seen": 3, "units_consumed": 1, "quota_used_today": 1}

    r2 = client.post(
        "/api/v1/sources/discover",
        json={"region": "US", "category": "", "max_results": 3},
    )
    assert r2.json()["imported"] == 0  # cache path: re-fetch updates, no dupes


def test_trends_sections_shape(client):
    client.post("/api/v1/sources/discover", json={"region": "US"})
    r = client.get("/api/v1/trends")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {
        "trending_now", "recently_rising", "fastest_growing", "top_categories",
    }
    assert len(body["trending_now"]) == 3
    assert body["top_categories"][0] == {"category": "gaming", "count": 3}


def test_trend_detail_404(client):
    assert client.get("/api/v1/trends/999").status_code == 404
