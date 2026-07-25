# Tests the file_dynamic_signal detector's scoring of execution-based signals.
import pytest

from backend.orchestrator.registry import get_registry


@pytest.fixture
def detector():
    return get_registry()["file_dynamic_signal"]


@pytest.mark.anyio
async def test_no_dynamic_signals_is_unknown(detector):
    d = await detector.score(b"x", {})
    assert d.verdict == "unknown"
    assert d.confidence == 0.0


@pytest.mark.anyio
async def test_not_executed_is_unknown(detector):
    d = await detector.score(b"x", {"dynamic_executed": "False", "dynamic_error": "not an ELF binary"})
    assert d.verdict == "unknown"
    assert d.confidence == 0.0


@pytest.mark.anyio
async def test_executed_with_no_red_flags_is_weak_benign(detector):
    d = await detector.score(b"x", {
        "dynamic_executed": "True",
        "dynamic_child_execs": "['/tmp/rk_dyn_x/sample']",
        "dynamic_connect_attempts": "[]",
        "dynamic_opens_outside_sandbox": "[]",
        "dynamic_timed_out": "False",
    })
    assert d.score == pytest.approx(0.5)
    # baseline 0.5 rounds to "malicious" per score >= 0.5 - same quirk as
    # file_sandbox_signal's baseline; low confidence keeps it from mattering
    assert d.verdict == "malicious"
    assert d.confidence == 0.15


@pytest.mark.anyio
async def test_connect_attempt_raises_score_and_confidence(detector):
    d = await detector.score(b"x", {
        "dynamic_executed": "True",
        "dynamic_child_execs": "['/tmp/rk_dyn_x/sample']",
        "dynamic_connect_attempts": "[{sa_family=AF_INET}]",
        "dynamic_opens_outside_sandbox": "[]",
        "dynamic_timed_out": "False",
    })
    assert d.score == pytest.approx(0.65)
    assert d.verdict == "malicious"
    assert d.confidence == 0.4


@pytest.mark.anyio
async def test_open_outside_sandbox_is_the_strongest_signal(detector):
    d = await detector.score(b"x", {
        "dynamic_executed": "True",
        "dynamic_child_execs": "['/tmp/rk_dyn_x/sample']",
        "dynamic_connect_attempts": "[]",
        "dynamic_opens_outside_sandbox": "['/home/victim/.ssh/id_rsa']",
        "dynamic_timed_out": "False",
    })
    assert d.score == pytest.approx(0.75)
    assert d.confidence == 0.4


@pytest.mark.anyio
async def test_spawned_child_process_adds_a_weak_bump(detector):
    d = await detector.score(b"x", {
        "dynamic_executed": "True",
        "dynamic_child_execs": "['/tmp/rk_dyn_x/sample', '/bin/true']",
        "dynamic_connect_attempts": "[]",
        "dynamic_opens_outside_sandbox": "[]",
        "dynamic_timed_out": "False",
    })
    assert d.score == pytest.approx(0.6)
    assert d.confidence == 0.15


@pytest.mark.anyio
async def test_timed_out_adds_a_weak_bump(detector):
    d = await detector.score(b"x", {
        "dynamic_executed": "True",
        "dynamic_child_execs": "['/tmp/rk_dyn_x/sample']",
        "dynamic_connect_attempts": "[]",
        "dynamic_opens_outside_sandbox": "[]",
        "dynamic_timed_out": "True",
    })
    assert d.score == pytest.approx(0.55)
    assert d.confidence == 0.15
