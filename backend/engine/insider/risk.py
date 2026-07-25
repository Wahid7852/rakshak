# Accumulates per-employee risk with time decay and maps it to a severity bucket.
from __future__ import annotations
import math, time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

RISK_DECAY_HALF_LIFE_S = 3 * 24 * 3600.0  # a lone anomaly fades to half its weight in 3 days
_RISK_DECAY_LAMBDA = math.log(2) / RISK_DECAY_HALF_LIFE_S

# Ordered high to low - severity_for() returns the first threshold the risk clears.
SEVERITY_THRESHOLDS = (("critical", 0.85), ("high", 0.65), ("medium", 0.40), ("low", 0.0))
CRITICAL_THRESHOLD = SEVERITY_THRESHOLDS[0][1]
MAX_RECENT_SIGNALS = 8
# EWMA of contribution-per-simulated-day, for eta_critical_days() below. Uses
# each event's own declared timestamp, not wall-clock - a demo backfills a
# month of history in seconds of real time, which would make a wall-clock
# rate meaningless. A real deployment scoring events as they actually happen
# would see event time and wall-clock converge anyway.
RATE_EWMA_ALPHA = 0.3


@dataclass
class RiskState:
    employee_id: str
    risk: float = 0.0
    last_update: float = field(default_factory=time.time)
    recent_signals: List[str] = field(default_factory=list)
    last_event_time: Optional[float] = None
    contribution_rate: float = 0.0  # risk/day, EWMA over event-time deltas


class RiskTracker:
    """Turns single-event anomaly contributions into a decayed, cumulative
    per-employee risk score.

    This is the low-false-positive mechanism the PS asks for: one anomalous
    event nudges risk up by a small, capped amount, which decays back down over
    a few days if nothing else happens. Severity only reaches high/critical when
    anomalies keep recurring (or several signal types line up) faster than they
    decay - a single off-hours login alone should never reach "high" on its own.
    """

    def __init__(self) -> None:
        self._states: Dict[str, RiskState] = {}

    def _decay(self, state: RiskState, now: float) -> None:
        elapsed = max(0.0, now - state.last_update)
        state.risk *= math.exp(-_RISK_DECAY_LAMBDA * elapsed)
        state.last_update = now

    def update(
        self,
        employee_id: str,
        contribution: float,
        reasons: List[str],
        now: Optional[float] = None,
        event_time: Optional[float] = None,
    ) -> RiskState:
        now = now if now is not None else time.time()
        state = self._states.get(employee_id)
        if state is None:
            state = RiskState(employee_id=employee_id, last_update=now)
            self._states[employee_id] = state
        self._decay(state, now)
        state.risk = min(1.0, state.risk + contribution)
        if reasons:
            state.recent_signals = (list(reasons) + state.recent_signals)[:MAX_RECENT_SIGNALS]

        if event_time is not None:
            if state.last_event_time is not None and event_time > state.last_event_time:
                elapsed_days = (event_time - state.last_event_time) / 86400.0
                instantaneous_rate = contribution / max(elapsed_days, 1e-6)
                state.contribution_rate = (
                    RATE_EWMA_ALPHA * instantaneous_rate + (1 - RATE_EWMA_ALPHA) * state.contribution_rate
                )
            state.last_event_time = event_time

        return state

    def state_for(self, employee_id: str) -> Optional[RiskState]:
        return self._states.get(employee_id)

    @staticmethod
    def severity_for(risk: float) -> str:
        for name, threshold in SEVERITY_THRESHOLDS:
            if risk >= threshold:
                return name
        return "low"


ETA_HORIZON_DAYS = 365.0  # beyond this, "projected" is noise, not a signal - report None, not a huge number


def eta_critical_days(state: RiskState) -> Optional[float]:
    """Projects days-to-critical at the current contribution rate. None if
    already critical, the rate is flat/negative, or the projection is so far
    out it isn't a meaningful trajectory (a near-zero rate can otherwise
    project millions of days, which is technically correct arithmetic and a
    useless number to show anyone)."""
    if state.risk >= CRITICAL_THRESHOLD or state.contribution_rate <= 0.0:
        return None
    eta = (CRITICAL_THRESHOLD - state.risk) / state.contribution_rate
    return eta if eta <= ETA_HORIZON_DAYS else None
