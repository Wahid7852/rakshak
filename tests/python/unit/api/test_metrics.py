# Tests the Prometheus metrics helpers directly.
from backend.observability.metrics import (
    QUARANTINE_COUNT,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    VERDICT_COUNT,
    record_quarantine,
    record_verdict,
    render_latest,
    track_request,
)
from backend.observability.request_id import get_request_id


def _counter_value(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


def test_track_request_records_status_and_latency():
    before = _counter_value(REQUEST_COUNT, protocol="http", endpoint="/test", status="200")

    with track_request("http", "/test") as outcome:
        outcome["status"] = "200"

    after = _counter_value(REQUEST_COUNT, protocol="http", endpoint="/test", status="200")
    assert after == before + 1

    sample_count = REQUEST_LATENCY.labels(protocol="http", endpoint="/test")._sum.get()
    assert sample_count >= 0.0


def test_track_request_defaults_to_error_status_on_unset():
    before = _counter_value(REQUEST_COUNT, protocol="http", endpoint="/unset-test", status="error")

    with track_request("http", "/unset-test"):
        pass  # never set outcome["status"]

    after = _counter_value(REQUEST_COUNT, protocol="http", endpoint="/unset-test", status="error")
    assert after == before + 1


def test_track_request_still_records_on_exception():
    before = _counter_value(REQUEST_COUNT, protocol="http", endpoint="/exc-test", status="error")

    try:
        with track_request("http", "/exc-test"):
            raise ValueError("boom")
    except ValueError:
        pass

    after = _counter_value(REQUEST_COUNT, protocol="http", endpoint="/exc-test", status="error")
    assert after == before + 1


def test_track_request_binds_and_resets_a_request_id():
    assert get_request_id() == "-"

    with track_request("http", "/rid-test") as outcome:
        rid_during = get_request_id()
        outcome["status"] = "200"

    assert rid_during != "-"
    assert get_request_id() == "-"


def test_record_verdict_increments_the_right_label():
    before = _counter_value(VERDICT_COUNT, kind="file", verdict="malicious")
    record_verdict("file", "malicious")
    after = _counter_value(VERDICT_COUNT, kind="file", verdict="malicious")
    assert after == before + 1


def test_record_quarantine_increments_counter():
    before = QUARANTINE_COUNT._value.get()
    record_quarantine()
    after = QUARANTINE_COUNT._value.get()
    assert after == before + 1


def test_render_latest_returns_prometheus_text_format():
    record_verdict("log", "benign")
    body, content_type = render_latest()
    assert b"rakshak_verdicts_total" in body
    assert "text/plain" in content_type
