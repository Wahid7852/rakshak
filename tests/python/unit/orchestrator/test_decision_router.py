# Tests decision router behavior.
from unittest.mock import AsyncMock

import pytest

from backend.orchestrator.decision import Event, Router, choose_route_for, fuse
from backend.orchestrator.types import Decision

@pytest.mark.anyio
async def test_router_runs_with_defaults():
    r = Router()
    d = await r.decide(Event(kind="log", payload="test line", context={}))
    assert d.verdict in ("malicious","benign","unknown")


def test_choose_route_for_log():
    plan = choose_route_for("log")
    assert plan.sequence == ["log_ngram", "log_hst", "log_sgd"]


def test_choose_route_for_file():
    plan = choose_route_for("file")
    assert plan.sequence == [
        "file_static", "file_ml_or_rf", "file_sandbox_signal", "file_dynamic_signal", "file_qsvc",
    ]


def test_fuse_no_decisions_is_unknown():
    d = fuse([])
    assert d == Decision(0.5, 0.0, "unknown", "fuse:none")


def test_fuse_weights_by_confidence():
    decisions = [
        Decision(0.9, 0.8, "malicious", "a"),
        Decision(0.1, 0.2, "benign", "b"),
    ]
    d = fuse(decisions)
    expected_score = (0.9 * 0.8 + 0.1 * 0.2) / (0.8 + 0.2)
    assert d.score == pytest.approx(expected_score)
    assert d.confidence == pytest.approx(min(1.0, (0.8 + 0.2) / 2))


def _fake_detector(decision: Decision):
    detector = AsyncMock(cost_ms_estimate=1)
    detector.score = AsyncMock(return_value=decision)
    return detector


@pytest.mark.anyio
async def test_router_short_circuits_on_confident_malicious():
    r = Router()
    r.registry["log_ngram"] = _fake_detector(Decision(0.9, 0.9, "malicious", "fake"))
    r.registry["log_hst"] = _fake_detector(Decision(0.1, 0.9, "benign", "fake"))
    r.registry["log_sgd"] = _fake_detector(Decision(0.1, 0.9, "benign", "fake"))

    result = await r.decide(Event(kind="log", payload="x", context={}))

    assert result.verdict == "malicious"
    r.registry["log_hst"].score.assert_not_called()
    r.registry["log_sgd"].score.assert_not_called()


@pytest.mark.anyio
async def test_router_short_circuits_on_confident_benign():
    r = Router()
    r.registry["log_ngram"] = _fake_detector(Decision(0.1, 0.9, "benign", "fake"))
    r.registry["log_hst"] = _fake_detector(Decision(0.9, 0.9, "malicious", "fake"))
    r.registry["log_sgd"] = _fake_detector(Decision(0.9, 0.9, "malicious", "fake"))

    result = await r.decide(Event(kind="log", payload="x", context={}))

    assert result.verdict == "benign"
    r.registry["log_hst"].score.assert_not_called()
    r.registry["log_sgd"].score.assert_not_called()


@pytest.mark.anyio
async def test_router_skips_qsvc_when_fused_score_not_borderline():
    r = Router()
    weak_benign = Decision(0.1, 0.3, "benign", "fake")  # low confidence: no early return
    r.registry["file_static"] = _fake_detector(weak_benign)
    r.registry["file_ml_or_rf"] = _fake_detector(weak_benign)
    r.registry["file_sandbox_signal"] = _fake_detector(weak_benign)
    r.registry["file_qsvc"] = _fake_detector(Decision(0.5, 0.9, "malicious", "fake"))

    await r.decide(Event(kind="file", payload=b"x", context={}))

    r.registry["file_qsvc"].score.assert_not_called()


@pytest.mark.anyio
async def test_router_calls_qsvc_when_fused_score_is_borderline():
    r = Router()
    borderline = Decision(0.5, 0.3, "benign", "fake")  # low confidence, sits inside the band
    r.registry["file_static"] = _fake_detector(borderline)
    r.registry["file_ml_or_rf"] = _fake_detector(borderline)
    r.registry["file_sandbox_signal"] = _fake_detector(borderline)
    r.registry["file_qsvc"] = _fake_detector(Decision(0.5, 0.9, "malicious", "fake"))

    await r.decide(Event(kind="file", payload=b"x", context={}))

    r.registry["file_qsvc"].score.assert_called_once()
