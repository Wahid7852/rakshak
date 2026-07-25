# Provides shared authentication metadata for gRPC clients.
from backend.api.config import settings

API_KEY_HEADER = "x-api-key"


def auth_metadata() -> tuple[tuple[str, str], ...]:
    if not settings.require_api_key:
        return ()
    return ((API_KEY_HEADER, settings.api_key),)
