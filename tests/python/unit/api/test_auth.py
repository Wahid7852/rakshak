# Tests verify_api_key's HMAC comparison and require_api_key toggle.
import pytest
from fastapi import HTTPException

from backend.api.config import ApiSettings
import backend.api.security.auth as auth_module


def _settings(**overrides):
    defaults = {"api_key": "s3cr3t", "require_api_key": True}
    defaults.update(overrides)
    return ApiSettings(**defaults)


def test_verify_api_key_accepts_correct_key(monkeypatch):
    monkeypatch.setattr(auth_module, "settings", _settings())
    assert auth_module.verify_api_key(x_api_key="s3cr3t") is True


def test_verify_api_key_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(auth_module, "settings", _settings())
    with pytest.raises(HTTPException) as exc_info:
        auth_module.verify_api_key(x_api_key="wrong")
    assert exc_info.value.status_code == 401


def test_verify_api_key_rejects_empty_key(monkeypatch):
    monkeypatch.setattr(auth_module, "settings", _settings())
    with pytest.raises(HTTPException):
        auth_module.verify_api_key(x_api_key="")


def test_verify_api_key_bypassed_when_not_required(monkeypatch):
    monkeypatch.setattr(auth_module, "settings", _settings(require_api_key=False))
    # even a wrong key is accepted once the requirement is off
    assert auth_module.verify_api_key(x_api_key="wrong") is True
