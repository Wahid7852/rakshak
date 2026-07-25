# Tests env-var parsing for backend API settings.
import pytest

from backend.api.config import _env_bool, load_settings


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0", False),
        ("false", False),
        ("False", False),
        ("no", False),
        ("off", False),
        ("1", True),
        ("true", True),
        ("yes", True),
        ("anything-else", True),
    ],
)
def test_env_bool_parses_common_truthy_falsy_strings(monkeypatch, raw, expected):
    monkeypatch.setenv("RAKSHAK_TEST_FLAG", raw)
    assert _env_bool("RAKSHAK_TEST_FLAG", default=not expected) is expected


def test_env_bool_uses_default_when_unset(monkeypatch):
    monkeypatch.delenv("RAKSHAK_TEST_FLAG", raising=False)
    assert _env_bool("RAKSHAK_TEST_FLAG", default=True) is True
    assert _env_bool("RAKSHAK_TEST_FLAG", default=False) is False


def test_load_settings_reads_env_overrides(monkeypatch):
    monkeypatch.setenv("RAKSHAK_APP_NAME", "custom-name")
    monkeypatch.setenv("RAKSHAK_VERSION", "9.9.9")
    monkeypatch.setenv("RAKSHAK_API_KEY", "custom-key")
    monkeypatch.setenv("RAKSHAK_REQUIRE_API_KEY", "0")

    settings = load_settings()

    assert settings.app_name == "custom-name"
    assert settings.version == "9.9.9"
    assert settings.api_key == "custom-key"
    assert settings.require_api_key is False


def test_load_settings_defaults_when_unset(monkeypatch):
    for var in ("RAKSHAK_APP_NAME", "RAKSHAK_VERSION", "RAKSHAK_API_KEY", "RAKSHAK_REQUIRE_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    settings = load_settings()

    assert settings.app_name == "RAKSHAK Backend"
    assert settings.version == "0.1.0"
    assert settings.api_key == "dev-key"
    assert settings.require_api_key is True


def test_quarantine_dir_defaults_to_none(monkeypatch):
    monkeypatch.delenv("RAKSHAK_QUARANTINE_DIR", raising=False)
    assert load_settings().quarantine_dir is None


def test_quarantine_dir_reads_env_override(monkeypatch):
    monkeypatch.setenv("RAKSHAK_QUARANTINE_DIR", "/var/lib/rakshak/quarantine")
    assert load_settings().quarantine_dir == "/var/lib/rakshak/quarantine"
