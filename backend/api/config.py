# Loads backend API configuration from the environment.
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ApiSettings:
    app_name: str = "RAKSHAK Backend"
    version: str = "0.1.0"
    api_key: str = "dev-key"
    require_api_key: bool = True
    max_file_bytes: int = 32 * 1024 * 1024
    quarantine_dir: str | None = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def load_settings() -> ApiSettings:
    return ApiSettings(
        app_name=os.getenv("RAKSHAK_APP_NAME", "RAKSHAK Backend"),
        version=os.getenv("RAKSHAK_VERSION", "0.1.0"),
        api_key=os.getenv("RAKSHAK_API_KEY", "dev-key"),
        require_api_key=_env_bool("RAKSHAK_REQUIRE_API_KEY", True),
        max_file_bytes=_env_positive_int("RAKSHAK_MAX_FILE_BYTES", 32 * 1024 * 1024),
        quarantine_dir=os.getenv("RAKSHAK_QUARANTINE_DIR"),
    )


settings = load_settings()
