# Provides RAKSHAK support for auth.
import hmac
from fastapi import Header, HTTPException

from backend.api.config import settings

API_KEY_HEADER = "x-api-key"


def verify_api_key(x_api_key: str = Header(default="")):
    if not settings.require_api_key:
        return True
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True
