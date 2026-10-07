"""Generate route tests — fake editorial service (no LLM)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.editorial import get_editorial_service
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.domain.editorial import service as editorial
from app.main import create_app
from tests.editorial.test_editorial import ScriptedLLM, _plan_dict


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
    return TestClient(app), app, factory


def _seed(setup, n=3):
    client, app, factory = setup
    db = factory()
    src = models.Source(provider="youtube", external_id="g", url="",
                        title="Show")
    db.add(src)
    db.flush()
    mids = []
    for i in range(n):
        m = models.Moment(source_id=src.id, start_time=float(i * 10),
                          end_time=float(i * 10 + 8),
                          transcript_excerpt=f"clip {i}", final_score=80.0,
                          status="APPROVED")
        db.add(m)
        db.flush()
        mids.append(m.id)
    ep = models.Episode(title="Draft", target_duration=1200.0)
    db.add(ep)
    db.commit()
    epid = ep.id
    db.close()

    def fake_service():
        # plan reversed order to prove the model (not scores) decides
        return editorial.EditorialService(
            ScriptedLLM([_plan_dict(list(reversed(mids)))]))

    app.dependency_overrides[get_editorial_service] = fake_service
    return epid, mids


def _clean_storyboards(epid):
    from pathlib import Path

    from app.services.ffmpeg_service import repo_data_dir

    p = repo_data_dir() / "storyboards" / f"{epid}.json"
    p.unlink(missing_ok=True)


def test_generate_applies_model_order(setup):
    client, _, _ = setup
    epid, mids = _seed(setup)
    try:
        r = client.post(f"/api/v1/episodes/{epid}/generate", json={})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["plan"]["title"] == "Test Show"
        clips = [s for s in body["episode"]["segments"]
                 if s["kind"] == "clip"]
        assert [c["moment_id"] for c in clips] == list(reversed(mids))
        assert body["episode"]["title"] == "Test Show"
    finally:
        _clean_storyboards(epid)


def test_generate_400s(setup):
    client, app, factory = setup
    assert client.post("/api/v1/episodes/999/generate",
                       json={}).status_code == 404
    epid, _ = _seed(setup, n=0)
    try:
        assert client.post(f"/api/v1/episodes/{epid}/generate",
                           json={}).status_code == 400
    finally:
        _clean_storyboards(epid)

    def broken():
        return editorial.EditorialService(ScriptedLLM([{"junk": 1}]))

    epid2, _ = _seed(setup)
    app.dependency_overrides[get_editorial_service] = broken
    try:
        assert client.post(f"/api/v1/episodes/{epid2}/generate",
                           json={}).status_code == 400
    finally:
        _clean_storyboards(epid2)
