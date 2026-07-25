# Tests that the incident narrative stays grounded in the real signals passed in.
from backend.engine.insider.narrative import build_narrative


def test_low_severity_narrative_has_no_signal_list():
    text = build_narrative("EMP001", "low", 0.1, "login", [])
    assert "EMP001" in text
    assert "Recent signals" not in text


def test_medium_plus_narrative_includes_real_signals_verbatim():
    signals = ["login from a host not seen before for this employee", "activity outside normal working hours"]
    text = build_narrative("EMP002", "critical", 0.95, "login", signals)
    assert "EMP002" in text
    assert "critical" in text
    for s in signals:
        assert s in text


def test_narrative_never_invents_signals_not_passed_in():
    text = build_narrative("EMP003", "high", 0.7, "data_transfer", ["transfer to a destination not seen before"])
    assert "transfer to a destination not seen before" in text
    assert "resignation" not in text  # nothing about HR/lifecycle unless it was actually in the signal list


def test_narrative_dedupes_repeated_signals():
    signals = ["activity outside normal working hours"] * 4
    text = build_narrative("EMP004", "medium", 0.5, "file_access", signals)
    assert text.count("activity outside normal working hours") == 1


def test_medium_plus_with_no_signals_still_returns_lead_sentence():
    text = build_narrative("EMP005", "medium", 0.45, "login", [])
    assert "EMP005" in text
    assert "0.45" in text


def test_blast_radius_and_eta_appear_when_provided():
    text = build_narrative(
        "EMP006", "high", 0.7, "data_transfer", [], blast_radius_bytes=50_000_000, eta_critical_days=2.3
    )
    assert "MB" in text or "GB" in text
    assert "2.3" in text


def test_blast_radius_and_eta_omitted_when_absent():
    text = build_narrative("EMP007", "high", 0.7, "data_transfer", [])
    assert "trailing 14 days" not in text
    assert "critical in" not in text


def test_low_severity_never_shows_blast_radius_or_eta():
    text = build_narrative("EMP008", "low", 0.1, "login", [], blast_radius_bytes=999_999, eta_critical_days=1.0)
    assert "trailing 14 days" not in text
    assert "critical in" not in text
