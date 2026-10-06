"""Moments route tests — keyword-only scoring (no model download)."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.moments import get_embedder
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.main import create_app
from tests.clipping.test_clipping import GOLDEN_SEGMENTS, GOLDEN_TITLE


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
    app.dependency_overrides[get_embedder] = lambda: None
    return TestClient(app), factory


def _seed(setup) -> int:
    client, factory = setup
    src_id = client.post("/api/v1/sources", json={
        "external_id": "s6fix", "title": GOLDEN_TITLE,
    }).json()["id"]
    db = factory()
    db.add(models.Transcript(
        source_id=src_id, language="en", model="test",
        text="t", segments_json=json.dumps(GOLDEN_SEGMENTS),
        audio_sha256="x",
    ))
    db.commit()
    db.close()
    return src_id


def test_find_moments_and_ranked_reads(setup):
    client, _ = setup
    src_id = _seed(setup)
    r = client.post(f"/api/v1/sources/{src_id}/find-moments",
                    json={"top_k": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] > 0 and len(body["top"]) == min(10, body["total"])
    assert body["top"][0]["start"] == pytest.approx(10.0, abs=2.0)

    listed = client.get(f"/api/v1/moments?source_id={src_id}").json()
    scores = [m["final_score"] for m in listed]
    assert scores == sorted(scores, reverse=True)
    assert listed[0]["moment_type"] in ("highlight", "question")

    single = client.get(f"/api/v1/moments/{listed[0]['id']}")
    assert single.status_code == 200
    assert single.json()["source_id"] == src_id


def test_find_moments_404_and_400(setup):
    client, _ = setup
    assert client.post("/api/v1/sources/999/find-moments",
                       json={}).status_code == 404
    bare = client.post("/api/v1/sources", json={
        "external_id": "bare", "title": "bare",
    }).json()["id"]
    assert client.post(f"/api/v1/sources/{bare}/find-moments",
                       json={}).status_code == 400
    assert client.get("/api/v1/moments/999").status_code == 404
