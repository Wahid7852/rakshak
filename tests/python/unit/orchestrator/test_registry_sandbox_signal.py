# Tests the file_sandbox_signal detector's entropy/format/suspicious-string scoring.
import pytest

from backend.orchestrator.registry import get_registry


@pytest.fixture
def detector():
    return get_registry()["file_sandbox_signal"]


@pytest.mark.anyio
async def test_no_sandbox_bytes_is_unknown(detector):
    d = await detector.score(b"", {})
    assert d.verdict == "unknown"
    assert d.confidence == 0.0


@pytest.mark.anyio
async def test_sandbox_error_is_unknown(detector):
    d = await detector.score(b"x", {"sandbox_bytes": "10", "sandbox_error": "analysis worker failed"})
    assert d.verdict == "unknown"
    assert d.confidence == 0.0


@pytest.mark.anyio
async def test_executable_format_alone_is_weak_malicious(detector):
    d = await detector.score(b"x", {"sandbox_bytes": "10", "sandbox_format": "pe"})
    assert d.score == pytest.approx(0.55)
    assert d.verdict == "malicious"
    assert d.confidence == 0.15  # no strong signal present, low confidence


@pytest.mark.anyio
async def test_high_entropy_raises_score_and_confidence(detector):
    d = await detector.score(b"x", {"sandbox_bytes": "10", "sandbox_entropy": "7.9"})
    assert d.score == pytest.approx(0.65)
    assert d.confidence == 0.35


@pytest.mark.anyio
async def test_suspicious_strings_raise_score_and_confidence(detector):
    d = await detector.score(
        b"x", {"sandbox_bytes": "10", "sandbox_suspicious_strings": "['powershell']"}
    )
    assert d.score == pytest.approx(0.6)
    assert d.confidence == 0.35


@pytest.mark.anyio
async def test_executable_disguised_as_document_is_format_mismatch(detector):
    d = await detector.score(
        b"x", {"sandbox_bytes": "10", "sandbox_format": "pe", "path": "invoice.txt"}
    )
    # fmt bonus (0.05) + mismatch bonus (0.2) on top of the 0.5 baseline
    assert d.score == pytest.approx(0.75)
    assert d.confidence == 0.35


@pytest.mark.anyio
async def test_timed_out_bumps_score_but_not_confidence(detector):
    d = await detector.score(b"x", {"sandbox_bytes": "10", "sandbox_timed_out": "true"})
    assert d.score == pytest.approx(0.55)
    assert d.confidence == 0.15  # timed_out isn't a "strong signal" for confidence purposes
