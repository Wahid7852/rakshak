# testing inference api, this crashed ungracefully before
from __future__ import annotations
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient
from backend.api.main import app
from backend.api.routers import scan as scan_router

client = TestClient(app)


def test_health_endpoint_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "RAKSHAK Backend", "version": "0.1.0"}


def test_healthz_endpoint_ok():
    r = client.get("/v1/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "RAKSHAK Backend", "version": "0.1.0"}


def test_scan_logline_requires_api_key():
    r = client.post("/v1/scan/logline", json={"line": "auth fail 10.0.0.1"})
    assert r.status_code == 401


def test_scan_logline_ok():
    r = client.post(
        "/v1/scan/logline",
        json={"line": "auth fail 10.0.0.1"},
        headers={"x-api-key": "dev-key"},
    )
    assert r.status_code == 200
    data = r.json()
    assert {"suspicious", "score", "confidence", "model", "reason"} <= set(data)
    assert 0.0 <= data["score"] <= 1.0


def test_scan_logline_rejects_empty_input():
    r = client.post(
        "/v1/scan/logline",
        json={"line": ""},
        headers={"x-api-key": "dev-key"},
    )
    assert r.status_code == 422


def test_scan_file_ok():
    r = client.post(
        "/v1/scan/file",
        files={"file": ("sample.bin", b"MZpayload", "application/octet-stream")},
        headers={"x-api-key": "dev-key"},
    )
    assert r.status_code == 200
    data = r.json()
    assert {"malicious", "score", "confidence", "model", "reason", "sha256"} <= set(data)
    assert len(data["sha256"]) == 64
    assert 0.0 <= data["score"] <= 1.0


def test_scan_file_rejects_empty_payload():
    r = client.post(
        "/v1/scan/file",
        files={"file": ("empty.bin", b"", "application/octet-stream")},
        headers={"x-api-key": "dev-key"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "file payload is empty"


def test_scan_file_enforces_size_limit(monkeypatch):
    monkeypatch.setattr(scan_router, "MAX_FILE_BYTES", 4)
    r = client.post(
        "/v1/scan/file",
        files={"file": ("large.bin", b"12345", "application/octet-stream")},
        headers={"x-api-key": "dev-key"},
    )
    assert r.status_code == 413
    assert r.json()["detail"] == "file exceeds 4 byte limit"
