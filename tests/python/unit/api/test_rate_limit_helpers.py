# Tests rate-limit key derivation and the monkeypatchable rate accessors.
from unittest.mock import MagicMock

import backend.api.security.rate_limit as rate_limit_module
from backend.api.security.rate_limit import _rate_limit_key, scan_file_rate, scan_logline_rate


def test_rate_limit_key_uses_api_key_header_when_present():
    request = MagicMock()
    request.headers = {"x-api-key": "some-key"}
    assert _rate_limit_key(request) == "some-key"


def test_rate_limit_key_falls_back_to_remote_address_without_api_key(monkeypatch):
    monkeypatch.setattr(rate_limit_module, "get_remote_address", lambda request: "1.2.3.4")
    request = MagicMock()
    request.headers = {}
    assert _rate_limit_key(request) == "1.2.3.4"


def test_rate_accessors_return_current_module_value(monkeypatch):
    monkeypatch.setattr(rate_limit_module, "_scan_file_rate", "5/minute")
    monkeypatch.setattr(rate_limit_module, "_scan_logline_rate", "50/minute")

    assert scan_file_rate() == "5/minute"
    assert scan_logline_rate() == "50/minute"
