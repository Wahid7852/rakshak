# Tests that scan endpoints actually throttle - they do real ML inference
# now, not instant lookups, so an unthrottled client can burn real CPU time.
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.security.rate_limit import _rate_limit_key, limiter

pytest.importorskip("fastapi")

client = TestClient(app)

# Auth only accepts one configured key ("dev-key" by default - see
# backend/api/security/auth.py) - reusing it here is fine because the
# reset_rate_limiter fixture below clears quota state before/after every
# test in this file, so usage can't leak between tests.
_HEADERS = {"x-api-key": "dev-key", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


def test_scan_logline_throttles_after_the_configured_limit(monkeypatch):
    monkeypatch.setattr("backend.api.security.rate_limit._scan_logline_rate", "3/minute")

    statuses = [
        client.post("/v1/scan/logline", json={"line": "test line"}, headers=_HEADERS).status_code
        for _ in range(5)
    ]

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3:] == [429, 429]


def test_rate_limit_key_is_derived_from_api_key_not_ip():
    """Two requests from the same IP but different x-api-key values must get
    independent quotas - otherwise clients sharing a NAT/proxy would throttle
    each other, and one leaked key couldn't be throttled without collateral
    damage to every other client behind the same address."""

    class _FakeRequest:
        def __init__(self, api_key):
            self.headers = {"x-api-key": api_key} if api_key else {}
            self.client = type("_C", (), {"host": "10.0.0.1"})()
            self.scope = {}

    assert _rate_limit_key(_FakeRequest("key-a")) == "key-a"
    assert _rate_limit_key(_FakeRequest("key-b")) == "key-b"
    assert _rate_limit_key(_FakeRequest("key-a")) != _rate_limit_key(_FakeRequest("key-b"))
