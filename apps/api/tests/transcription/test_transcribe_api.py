"""Route/domain tests — Fake whisper (no model download in CI)."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.transcription import get_whisper_service
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.database import get_db
from app.main import create_app


class FakeWhisper:
    model_name = "fake-tiny"

    def transcribe(self, wav_path, language=None, word_timestamps=True):
        assert str(wav_path).endswith(".wav")
        return {
            "language": "en",
            "segments": [
                {"start": 0.0, "end": 1.1, "text": "Hello world.",
                 "confidence": -0.2,
                 "words": [
                     {"start": 0.0, "end": 0.5, "word": "Hello",
                      "probability": 0.99},
                     {"start": 0.5, "end": 1.1, "word": " world.",
                      "probability": 0.98},
                 ]},
            ],
            "text": "Hello world.",
        }


@pytest.fixture()
def setup(tmp_path):
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
    app.dependency_overrides[get_whisper_service] = lambda: FakeWhisper()
    return TestClient(app), factory, tmp_path


def _source_with_audio(setup) -> int:
    client, factory, tmp_path = setup
    src_id = client.post("/api/v1/sources", json={
        "external_id": "s5fix", "title": "S5",
    }).json()["id"]
    wav = tmp_path / "audio_16k.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 1000)
    db = factory()
    db.add(models.MediaAsset(source_id=src_id, kind="audio",
                             path=str(wav), codec="pcm_s16le"))
    db.commit()
    db.close()
    return src_id


def test_transcribe_creates_transcript_and_job(setup):
    client, factory, _ = setup
    src_id = _source_with_audio(setup)
    r = client.post(f"/api/v1/sources/{src_id}/transcribe", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["skipped"] is False
    assert body["segments"] == 1 and body["language"] == "en"

    db = factory()
    tr = db.query(models.Transcript).one()
    assert json.loads(tr.segments_json)[0]["words"][0]["word"] == "Hello"
    assert tr.audio_sha256 and len(tr.audio_sha256) == 64
    job = db.query(models.Job).filter_by(type="TRANSCRIBE").one()
    assert job.status == "COMPLETED" and job.progress == 1.0
    db.close()


def test_transcribe_idempotent_skip(setup):
    client, factory, _ = setup
    src_id = _source_with_audio(setup)
    first = client.post(f"/api/v1/sources/{src_id}/transcribe", json={}).json()
    second = client.post(f"/api/v1/sources/{src_id}/transcribe", json={}).json()
    assert second["skipped"] is True
    assert second["transcript_id"] == first["transcript_id"]
    db = factory()
    assert db.query(models.Transcript).count() == 1
    db.close()


def test_transcribe_force_reruns(setup):
    client, factory, _ = setup
    src_id = _source_with_audio(setup)
    client.post(f"/api/v1/sources/{src_id}/transcribe", json={})
    r = client.post(f"/api/v1/sources/{src_id}/transcribe",
                    json={"force": True})
    assert r.json()["skipped"] is False
    db = factory()
    assert db.query(models.Transcript).count() == 2
    db.close()


def test_get_transcript_and_404s(setup):
    client, _, _ = setup
    src_id = _source_with_audio(setup)
    assert client.get(f"/api/v1/sources/{src_id}/transcript").status_code == 404
    client.post(f"/api/v1/sources/{src_id}/transcribe", json={})
    r = client.get(f"/api/v1/sources/{src_id}/transcript")
    assert r.status_code == 200
    assert r.json()["segments"][0]["text"] == "Hello world."
    assert client.get("/api/v1/sources/999/transcript").status_code == 404
    assert client.post("/api/v1/sources/999/transcribe",
                       json={}).status_code == 404


def test_transcribe_without_assets_is_400(setup):
    client, _, _ = setup
    src_id = client.post("/api/v1/sources", json={
        "external_id": "bare", "title": "bare",
    }).json()["id"]
    r = client.post(f"/api/v1/sources/{src_id}/transcribe", json={})
    assert r.status_code == 400
