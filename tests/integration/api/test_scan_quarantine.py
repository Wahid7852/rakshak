# Tests that /v1/scan/file wires confident-malicious verdicts to real quarantine.
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.orchestrator.types import Decision

pytest.importorskip("fastapi")

client = TestClient(app)


def _scan(content: bytes = b"payload", filename: str = "sample.bin"):
    return client.post(
        "/v1/scan/file",
        headers={"x-api-key": "dev-key"},
        files={"file": (filename, content, "application/octet-stream")},
    )


@pytest.fixture(autouse=True)
def isolated_quarantine(tmp_path, monkeypatch):
    """Point the shared quarantine manager accessor at a scratch dir per test."""
    from backend.engine.quarantine import QuarantineManager

    manager = QuarantineManager(tmp_path / "quarantine")
    monkeypatch.setattr("backend.api.deps.get_quarantine_manager", lambda: manager)
    yield manager


def test_confident_malicious_file_gets_quarantined(isolated_quarantine):
    fake = Decision(0.95, 0.9, "malicious", "test")
    with patch("backend.api.routers.scan.router_runtime.decide", new=AsyncMock(return_value=fake)):
        r = _scan(b"evil content", "evil.exe")

    assert r.status_code == 200
    body = r.json()
    assert body["malicious"] is True
    assert body["quarantined"] is True
    assert body["quarantine_id"] is not None
    assert len(isolated_quarantine.list_quarantined()) == 1


def test_benign_file_is_not_quarantined(isolated_quarantine):
    fake = Decision(0.1, 0.8, "benign", "test")
    with patch("backend.api.routers.scan.router_runtime.decide", new=AsyncMock(return_value=fake)):
        r = _scan(b"fine content", "fine.txt")

    assert r.status_code == 200
    body = r.json()
    assert body["malicious"] is False
    assert body["quarantined"] is False
    assert body["quarantine_id"] is None
    assert isolated_quarantine.list_quarantined() == []


def test_low_confidence_malicious_is_not_quarantined(isolated_quarantine):
    """A fused score that nudged just past 0.5 with near-zero confidence
    shouldn't be enough to destroy someone's file - matches
    Router.decide()'s own confidence gate for a definitive verdict."""
    fake = Decision(0.51, 0.1, "malicious", "test")
    with patch("backend.api.routers.scan.router_runtime.decide", new=AsyncMock(return_value=fake)):
        r = _scan(b"ambiguous content", "ambiguous.bin")

    assert r.status_code == 200
    body = r.json()
    assert body["malicious"] is True
    assert body["quarantined"] is False
    assert isolated_quarantine.list_quarantined() == []
