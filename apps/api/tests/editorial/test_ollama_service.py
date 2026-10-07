"""Ollama adapter tests — MockTransport, never the network."""

import httpx
import pytest

from app.services.ollama_service import (
    OllamaError,
    OllamaService,
    model_for,
    parse_json_content,
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_chat_json_parses():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert b'"format": "json"' in body or b'"format":"json"' in body
        assert b'"think": false' in body or b'"think":false' in body
        return httpx.Response(200, json={
            "message": {"content": '{"title": "Hi"}'}})

    svc = OllamaService(model="m", client=_client(handler))
    assert svc.chat_json("sys", "user") == {"title": "Hi"}


def test_parse_strips_think_blocks():
    assert parse_json_content(
        '<think>reasoning here</think>\n{"title": "Hi"}') == {"title": "Hi"}
    with pytest.raises(ValueError, match="no JSON object"):
        parse_json_content("just words, no braces at all")


def test_chat_non_json_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "message": {"content": "not json {"}})

    with pytest.raises(OllamaError, match="non-JSON"):
        OllamaService(model="m", client=_client(handler)).chat_json("s", "u")


def test_chat_http_error_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(OllamaError, match="500"):
        OllamaService(model="m", client=_client(handler)).chat_json("s", "u")


def test_ping():
    ok = _client(lambda r: httpx.Response(200, json={"models": []}))
    down = _client(lambda r: httpx.Response(500, json={}))
    assert OllamaService(model="m", client=ok).ping() is True
    assert OllamaService(model="m", client=down).ping() is False


def test_model_for_roles():
    assert isinstance(model_for("classifier"), str)
    assert isinstance(model_for("editor"), str)
    assert model_for("editor", {"editor": "custom:1b"}) == "custom:1b"
    with pytest.raises(OllamaError, match="unknown model role"):
        model_for("nope")
