# Defines Prometheus metrics shared by the HTTP and gRPC entry points.
from __future__ import annotations
import time
from contextlib import contextmanager

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from backend.observability.request_id import bind_request_id, reset_request_id

REQUEST_COUNT = Counter(
    "rakshak_requests_total",
    "Requests handled, by protocol/endpoint/status.",
    ["protocol", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "rakshak_request_latency_seconds",
    "Request handling latency, by protocol/endpoint.",
    ["protocol", "endpoint"],
)

VERDICT_COUNT = Counter(
    "rakshak_verdicts_total",
    "Decision verdicts returned, by artifact kind and verdict.",
    ["kind", "verdict"],
)

QUARANTINE_COUNT = Counter(
    "rakshak_quarantine_total",
    "Files moved to quarantine.",
)


@contextmanager
def track_request(protocol: str, endpoint: str):
    """Times a request, records its outcome, and binds a request id so every log
    line emitted during the call carries it (see observability/request_id.py).
    Usage:

        with track_request("http", "/v1/scan/file") as outcome:
            ... do the work ...
            outcome["status"] = "200"
    """
    start = time.monotonic()
    outcome = {"status": "error"}
    token = bind_request_id()
    try:
        yield outcome
    finally:
        reset_request_id(token)
        REQUEST_LATENCY.labels(protocol=protocol, endpoint=endpoint).observe(time.monotonic() - start)
        REQUEST_COUNT.labels(protocol=protocol, endpoint=endpoint, status=outcome["status"]).inc()


def record_verdict(kind: str, verdict: str) -> None:
    VERDICT_COUNT.labels(kind=kind, verdict=verdict).inc()


def record_quarantine() -> None:
    QUARANTINE_COUNT.inc()


def render_latest() -> tuple[bytes, str]:
    """Returns (body, content_type) for a /metrics endpoint."""
    return generate_latest(), CONTENT_TYPE_LATEST
