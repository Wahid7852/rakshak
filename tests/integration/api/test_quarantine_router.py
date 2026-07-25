# Tests the REST quarantine list/restore/delete endpoints.
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app

pytest.importorskip("fastapi")

client = TestClient(app)

AUTH = {"x-api-key": "dev-key"}


@pytest.fixture(autouse=True)
def isolated_quarantine(tmp_path, monkeypatch):
    """Point the shared quarantine manager accessor at a scratch dir per test."""
    from backend.engine.quarantine import QuarantineManager

    manager = QuarantineManager(tmp_path / "quarantine")
    monkeypatch.setattr("backend.api.deps.get_quarantine_manager", lambda: manager)
    yield manager


def _quarantine_one(manager, tmp_path, name="evil.exe", content=b"evil content"):
    src = tmp_path / name
    src.write_bytes(content)
    entry = manager.quarantine_file(src, reason="test fixture")
    assert entry is not None
    return entry


def test_list_is_empty_with_no_quarantined_files():
    r = client.get("/v1/quarantine", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"entries": []}


def test_list_returns_a_quarantined_entry(isolated_quarantine, tmp_path):
    entry = _quarantine_one(isolated_quarantine, tmp_path)

    r = client.get("/v1/quarantine", headers=AUTH)
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["quarantine_id"] == entry.quarantine_id
    assert entries[0]["sha256"] == entry.sha256


def test_restore_round_trip(isolated_quarantine, tmp_path):
    entry = _quarantine_one(isolated_quarantine, tmp_path)

    r = client.post("/v1/quarantine/restore", headers=AUTH, json={"quarantine_id": entry.quarantine_id})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "quarantine_id": entry.quarantine_id}

    assert isolated_quarantine.list_quarantined() == []

    r2 = client.post("/v1/quarantine/restore", headers=AUTH, json={"quarantine_id": entry.quarantine_id})
    assert r2.status_code == 404


def test_delete_round_trip(isolated_quarantine, tmp_path):
    entry = _quarantine_one(isolated_quarantine, tmp_path)

    r = client.delete(f"/v1/quarantine/{entry.quarantine_id}", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "quarantine_id": entry.quarantine_id}

    assert isolated_quarantine.list_quarantined() == []

    r2 = client.delete(f"/v1/quarantine/{entry.quarantine_id}", headers=AUTH)
    assert r2.status_code == 404


def test_delete_unknown_id_is_404():
    r = client.delete("/v1/quarantine/does-not-exist", headers=AUTH)
    assert r.status_code == 404


@pytest.mark.parametrize(
    "make_request",
    [
        lambda: client.get("/v1/quarantine"),
        lambda: client.post("/v1/quarantine/restore", json={"quarantine_id": "x"}),
        lambda: client.delete("/v1/quarantine/x"),
    ],
)
def test_requires_api_key(make_request):
    r = make_request()
    assert r.status_code == 401
