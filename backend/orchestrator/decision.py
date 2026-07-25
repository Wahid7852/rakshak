# Coordinates backend orchestration for decision.
from __future__ import annotations
import asyncio, logging
from dataclasses import dataclass
from typing import List, Literal, Mapping, Optional

from .policies import Budgets, Thresholds
from .types import Decision
from .registry import get_registry

logger = logging.getLogger(__name__)

ArtifactKind = Literal[
    "log", "file", "insider_login", "insider_file_access", "insider_transfer", "insider_hr_signal",
]


@dataclass
class Event:
    kind: ArtifactKind
    payload: object
    context: Mapping[str, object]


@dataclass
class RoutePlan:
    name: str
    sequence: List[str]


_INSIDER_ROUTES = {
    "insider_login": RoutePlan("insider_login", ["insider_login_baseline"]),
    "insider_file_access": RoutePlan("insider_file_access", ["insider_file_baseline"]),
    "insider_transfer": RoutePlan("insider_transfer", ["insider_transfer_baseline"]),
    "insider_hr_signal": RoutePlan("insider_hr_signal", ["insider_hr_signal"]),
}


def choose_route_for(kind: ArtifactKind) -> RoutePlan:
    if kind == "log":
        return RoutePlan("log_fastpath", ["log_ngram", "log_hst", "log_sgd"])
    if kind in _INSIDER_ROUTES:
        return _INSIDER_ROUTES[kind]
    # Note: sandbox signal is a cheap mid-stage nudge. file_dynamic_signal only
    # does real work when RAKSHAK_SANDBOX_ADAPTER=dynamic is set (otherwise ctx
    # has no dynamic_* keys and it returns instantly) - placed after the cheap
    # detectors so a confident static verdict skips executing the sample at all.
    return RoutePlan(
        "file_cascade",
        ["file_static", "file_ml_or_rf", "file_sandbox_signal", "file_dynamic_signal", "file_qsvc"],
    )


def fuse(decisions: List[Decision]) -> Decision:
    if not decisions:
        return Decision(0.5, 0.0, "unknown", "fuse:none")
    tot = sum(d.confidence for d in decisions) or 1e-9
    score = sum(d.score * d.confidence for d in decisions) / tot
    conf = min(1.0, sum(d.confidence for d in decisions) / max(1, len(decisions)))
    verdict: Literal["malicious", "benign"] = "malicious" if score >= 0.5 else "benign"
    return Decision(score, conf, verdict, "fuse:weighted")


class Router:
    def __init__(self, budgets: Optional[Budgets] = None, thresholds: Optional[Thresholds] = None):
        self.budgets = budgets or Budgets()
        self.thr = thresholds or Thresholds()
        self.registry = get_registry()

    async def decide(self, ev: Event) -> Decision:
        plan = choose_route_for(ev.kind)
        if ev.kind == "log":
            budget_ms = self.budgets.LOG_MS
        elif ev.kind in _INSIDER_ROUTES:
            budget_ms = self.budgets.INSIDER_MS
        else:
            budget_ms = self.budgets.FILE_INIT_MS

        decisions: List[Decision] = []
        spent = 0.0
        for name in plan.sequence:
            det = self.registry[name]

            # Only run QSVM for borderline file cases
            if name == "file_qsvc" and decisions:
                fused = fuse(decisions)
                if not (self.thr.BORDERLINE_LOW <= fused.score <= self.thr.BORDERLINE_HIGH):
                    break

            try:
                d: Decision = await asyncio.wait_for(
                    det.score(ev.payload, ev.context),
                    timeout=max(0.001, det.cost_ms_estimate / 1000.0 + 0.05),
                )
            except Exception:
                logger.warning("detector %s failed/timed out, skipping", name, exc_info=True)
                continue

            decisions.append(d)
            fused = fuse(decisions)

            if fused.score >= self.thr.MALICIOUS and fused.confidence >= 0.5:
                return fused
            if fused.score <= self.thr.BENIGN and fused.confidence >= 0.5:
                return fused

            spent += det.cost_ms_estimate
            if spent >= budget_ms:
                break

        return fuse(decisions)
