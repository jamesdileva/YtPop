"""S2: tables exist + source create/read round-trip (isolated in-memory DB)."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.database import get_db
from app.main import create_app

EXPECTED_TABLES = {
    "sources",
    "trend_events",
    "trend_sources",
    "transcripts",
    "moments",
    "episodes",
    "episode_segments",
    "jobs",
    "rights_records",
    "renders",
}


def make_client() -> TestClient:
    from app.db import models  # noqa: F401  (register metadata)

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
    return TestClient(app)


def test_all_tables_exist():
    from app.db import models  # noqa: F401

    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES.issubset(tables), f"missing: {EXPECTED_TABLES - tables}"


def test_source_create_and_read():
    client = make_client()
    payload = {
        "provider": "youtube",
        "external_id": "abc123",
        "url": "https://youtube.com/watch?v=abc123",
        "title": "S2 fixture",
        "channel_name": "Test Channel",
        "category": "gaming",
    }
    r = client.post("/api/v1/sources", json=payload)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["external_id"] == "abc123"

    r2 = client.get(f"/api/v1/sources/{created['id']}")
    assert r2.status_code == 200
    assert r2.json()["title"] == "S2 fixture"

    r3 = client.get("/api/v1/sources")
    assert r3.status_code == 200
    assert len(r3.json()) == 1


def test_source_404():
    client = make_client()
    r = client.get("/api/v1/sources/9999")
    assert r.status_code == 404
