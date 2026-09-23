"""Testes técnicos; não representam validação de doses nem de condutas clínicas."""
import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from deploy.server import create_app, MAX_BODY_BYTES

TEST_TOKEN = "test-only-" + "a" * 48

@pytest.fixture
def protected(monkeypatch):
    monkeypatch.setenv("NEXO_API_TOKEN", TEST_TOKEN)
    return create_app()

@pytest.fixture
def client(protected):
    return TestClient(protected)

@pytest.mark.parametrize("value", [None, "", "short", "a" * 31, "a" * 257, "a" * 40 + " ", "á" * 40])
def test_startup_fails_without_valid_secret(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("NEXO_API_TOKEN", raising=False)
    else:
        monkeypatch.setenv("NEXO_API_TOKEN", value)
    with pytest.raises(RuntimeError):
        create_app()

@pytest.mark.parametrize("path", ["/", "/health"])
def test_public_status(client, path):
    result = client.get(path)
    assert result.status_code == 200
    assert result.headers["x-nexo-clinical-validation"] == "not-implemented"
    assert result.headers["cache-control"] == "no-store"
    assert TEST_TOKEN not in result.text

@pytest.mark.parametrize("path", ["/v1/sources", "/v1/capabilities", "/docs", "/redoc", "/openapi.json", "/health/", "/unknown"])
def test_every_other_path_requires_auth(client, path):
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"

@pytest.mark.parametrize("value", ["Bearer invalid", "Basic " + TEST_TOKEN, "Bearer", "Bearer " + TEST_TOKEN + "extra"])
def test_wrong_auth(client, value):
    assert client.get("/v1/sources", headers={"Authorization": value}).status_code == 401

def test_auth_and_real_backend(client):
    response = client.post("/v1/orchestrate", headers={"Authorization": "Bearer " + TEST_TOKEN}, json={"text": "ECG com taquicardia"})
    assert response.status_code == 200
    assert "Cardiologia e ECG" in response.json()["specialists"]

def test_capabilities_truthful(client):
    r = client.get("/v1/capabilities", headers={"Authorization": "Bearer " + TEST_TOKEN})
    assert r.status_code == 200
    assert r.json()["clinical_validation"] is False
    assert r.json()["live_evidence_search"] is False
    assert r.json()["sites_integration_verified"] is False

def test_no_cors_wildcard(client):
    response = client.get("/health", headers={"Origin": "https://example.invalid"})
    assert "access-control-allow-origin" not in response.headers

def test_oversized_body(client):
    result = client.post("/v1/orchestrate", headers={"Authorization": "Bearer " + TEST_TOKEN}, content=b"x" * (MAX_BODY_BYTES + 1))
    assert result.status_code == 413

def test_rejects_duplicate_authorization(client):
    result = client.get("/v1/sources", headers=[("Authorization", "Bearer " + TEST_TOKEN), ("Authorization", "Bearer " + TEST_TOKEN)])
    assert result.status_code == 401

def test_stream_without_content_length_is_limited(protected):
    async def run():
        events = []
        chunks = iter([
            {"type": "http.request", "body": b"x" * 600_000, "more_body": True},
            {"type": "http.request", "body": b"x" * 600_000, "more_body": False},
        ])
        async def receive():
            return next(chunks)
        async def send(message):
            events.append(message)
        scope = {"type": "http", "method": "POST", "path": "/v1/orchestrate", "headers": [(b"authorization", ("Bearer " + TEST_TOKEN).encode())], "http_version": "1.1", "scheme": "https", "query_string": b"", "root_path": "", "server": ("test", 443), "client": ("127.0.0.1", 12345)}
        await protected(scope, receive, send)
        assert events[0]["status"] == 413
    asyncio.run(run())
