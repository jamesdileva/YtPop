"""D7 embedding backends: MiniLM, Ollama fallback, resolution order."""

import json

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import models  # noqa: F401
from app.db.base import Base
from app.services import embedding_service as emb


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _source_with_features(db):
    src = models.Source(provider="youtube",
                       external_id="emb-backend", url="",
                       title="Embedding backend")
    db.add(src)
    db.flush()
    db.add(models.Transcript(
        source_id=src.id, language="en", model="test", text="t",
        segments_json=json.dumps([
            {"start": 0.0, "end": 6.0, "text": "Wow, amazing!", "words": []},
            {"start": 6.0, "end": 12.0, "text": "The final answer.",
             "words": []}]),
        audio_sha256="x"))
    db.commit()
    return src.id


def test_ollama_embedder_normalizes():
    def handler(request: httpx.Request) -> httpx.Response:
        assert b"nomic-embed-text" in request.read()
        return httpx.Response(200, json={
            "embeddings": [[3.0, 4.0], [0.0, 2.0]]})

    embedder = emb.OllamaEmbedder(
        client=httpx.Client(transport=httpx.MockTransport(handler)))
    vecs = embedder.encode(["a", "b"])
    assert len(vecs) == 2
    assert abs(sum(x * x for x in vecs[0]) - 1.0) < 1e-6
    assert abs(sum(x * x for x in vecs[1]) - 1.0) < 1e-6


def test_ollama_embedder_rejects_bad_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [[1.0]]})

    embedder = emb.OllamaEmbedder(
        client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(RuntimeError, match="embeddings"):
        embedder.encode(["a", "b"])


def test_ollama_embedder_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    embedder = emb.OllamaEmbedder(
        client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(RuntimeError, match="500"):
        embedder.encode(["a"])


def test_resolution_order_prefers_local(monkeypatch):
    monkeypatch.setattr(emb, "local_available", lambda: True)
    monkeypatch.setattr(emb, "ollama_available", lambda: True)
    assert isinstance(emb.resolve_embedder("auto"), emb.LocalMiniLM)


def test_resolution_falls_back_to_ollama(monkeypatch):
    monkeypatch.setattr(emb, "local_available", lambda: False)
    monkeypatch.setattr(emb, "ollama_available", lambda: True)
    assert isinstance(emb.resolve_embedder("auto"), emb.OllamaEmbedder)


def test_resolution_none_when_no_backend(monkeypatch):
    monkeypatch.setattr(emb, "local_available", lambda: False)
    monkeypatch.setattr(emb, "ollama_available", lambda: False)
    assert emb.resolve_embedder("auto") is None


def test_explicit_backend_bypasses_autodetection(monkeypatch):
    monkeypatch.setattr(emb, "local_available", lambda: False)
    monkeypatch.setattr(emb, "ollama_available", lambda: True)
    assert isinstance(emb.resolve_embedder("ollama"), emb.OllamaEmbedder)
    # minilm requested but unavailable -> resolve returns None (the caller
    # raises a clear "no embedding backend" error) rather than crashing here
    monkeypatch.setattr(emb, "ollama_available", lambda: False)
    assert emb.resolve_embedder("minilm") is None


def test_clipping_reports_missing_backend(monkeypatch, db):
    """Keyword-only mode must fail loudly, not silently produce junk."""
    from app.domain.clipping import service as clipping

    monkeypatch.setattr(clipping, "default_embedder", lambda: None)
    src_id = _source_with_features(db)
    with pytest.raises(clipping.ClipError, match="embedding backend"):
        clipping.find_moments(db, src_id, use_embeddings=True)
