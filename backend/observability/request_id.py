# Correlates one request/RPC's log lines together via a per-call id, and gives
# both entry points a shared JSON-line log format to emit it in.
from __future__ import annotations
import contextvars, json, logging, uuid

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def get_request_id() -> str:
    return _request_id.get()


def bind_request_id(value: str | None = None) -> contextvars.Token:
    """Sets the active request id for the current task/thread; call reset_request_id
    with the returned token when the request/RPC ends, same pattern as ContextVar.set."""
    return _request_id.set(value or new_request_id())


def reset_request_id(token: contextvars.Token) -> None:
    _request_id.reset(token)


class RequestIdLogFilter(logging.Filter):
    """Injects the active request id into every LogRecord as %(request_id)s."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class JsonLogFormatter(logging.Formatter):
    """One JSON object per line. Uses json.dumps rather than a %-format string so a
    message containing quotes/newlines can't produce invalid JSON output."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_json_logging(level: int = logging.INFO) -> None:
    """Shared logging setup for both entry points (backend.api.server,
    backend.api.gRPC.decider_server): one JSON-line handler on the root logger, with
    the current request id attached to every record.

    Correlates log lines within a single HTTP request or gRPC call, not across a
    chain of services - there's no inbound trace-header propagation here, just a
    fresh id bound for the duration of each call (see track_request in metrics.py).
    """
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdLogFilter())
    handler.setFormatter(JsonLogFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
