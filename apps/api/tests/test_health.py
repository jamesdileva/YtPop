from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


def test_health_dependencies_shape():
    r = client.get("/api/v1/health/dependencies")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "dependencies" in body
    assert body["dependencies"]["api"] == "ok"
