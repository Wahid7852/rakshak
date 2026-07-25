# Tests request-id correlation and the JSON log formatter directly.
import json, logging

from backend.observability.request_id import (
    JsonLogFormatter,
    RequestIdLogFilter,
    bind_request_id,
    configure_json_logging,
    get_request_id,
    new_request_id,
    reset_request_id,
)


def test_get_request_id_defaults_to_placeholder_outside_any_binding():
    assert get_request_id() == "-"


def test_bind_and_reset_round_trip():
    before = get_request_id()
    token = bind_request_id("abc123")
    try:
        assert get_request_id() == "abc123"
    finally:
        reset_request_id(token)
    assert get_request_id() == before


def test_bind_without_a_value_generates_one():
    token = bind_request_id()
    try:
        rid = get_request_id()
        assert rid != "-"
        assert len(rid) == 12  # uuid4().hex[:12]
    finally:
        reset_request_id(token)


def test_new_request_id_values_are_unique():
    assert new_request_id() != new_request_id()


def test_request_id_log_filter_injects_active_id():
    token = bind_request_id("filter-test")
    try:
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello", None, None)
        RequestIdLogFilter().filter(record)
        assert record.request_id == "filter-test"
    finally:
        reset_request_id(token)


def test_configure_json_logging_installs_a_json_handler_on_the_root_logger():
    root = logging.getLogger()
    original_handlers, original_level = root.handlers[:], root.level
    try:
        configure_json_logging(level=logging.WARNING)
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, JsonLogFormatter)
        assert root.level == logging.WARNING
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_json_log_formatter_produces_valid_json_with_request_id():
    token = bind_request_id("fmt-test")
    try:
        record = logging.LogRecord("x", logging.INFO, __file__, 1, 'quote " and newline \n', None, None)
        RequestIdLogFilter().filter(record)
        line = JsonLogFormatter().format(record)
    finally:
        reset_request_id(token)

    payload = json.loads(line)
    assert payload["request_id"] == "fmt-test"
    assert payload["level"] == "INFO"
    assert 'quote " and newline' in payload["message"]
