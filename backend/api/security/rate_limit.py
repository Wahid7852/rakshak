# Rate limiting for scan endpoints. Keyed by API key, not raw IP, so it
# stays correct behind a proxy/NAT.
import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _rate_limit_key(request: Request) -> str:
    api_key = request.headers.get("x-api-key")
    return api_key if api_key else get_remote_address(request)


# functions, not plain strings, so slowapi re-reads them per request and
# tests can monkeypatch the value and have it take effect
_scan_file_rate = os.environ.get("RAKSHAK_RATE_SCAN_FILE", "30/minute")
_scan_logline_rate = os.environ.get("RAKSHAK_RATE_SCAN_LOGLINE", "300/minute")
_quarantine_mutate_rate = os.environ.get("RAKSHAK_RATE_QUARANTINE_MUTATE", "60/minute")


def scan_file_rate() -> str:
    return _scan_file_rate


def scan_logline_rate() -> str:
    return _scan_logline_rate


def quarantine_mutate_rate() -> str:
    return _quarantine_mutate_rate


limiter = Limiter(key_func=_rate_limit_key)
