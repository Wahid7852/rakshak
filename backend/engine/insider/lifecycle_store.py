# Tracks per-employee HR/lifecycle state (resignation, offboarding, PIP) as a risk multiplier.
from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Dict, Optional

# (multiplier, window_days). The PS's own flagship scenario is "quietly
# accessing sensitive files before resignation" - nothing in login/file/
# transfer logs says *why* behavior changed, so this is a deliberately
# out-of-PS 4th signal type that amplifies whatever the behavioral engine
# already finds, rather than being a detector on its own. A departing
# employee isn't inherently guilty - the multiplier only matters when it's
# multiplying a real anomaly, never an isolated trigger by itself.
_SIGNAL_EFFECT = {
    "resignation_submitted": (1.75, 45),
    "offboarding_scheduled": (1.75, 45),
    "performance_improvement_plan": (1.3, 30),
    "role_change": (1.0, 0),  # recorded for context, no risk effect
}
DEFAULT_MULTIPLIER = 1.0


@dataclass
class LifecycleState:
    employee_id: str
    signal_type: str
    multiplier: float
    recorded_at: float
    expires_at: float


class LifecycleStore:
    """One active lifecycle signal per employee - a newer signal replaces an
    older one rather than stacking multipliers, so a PIP followed by a
    resignation reads as "now in a departing window", not a compounding
    penalty for having been on a PIP earlier."""

    def __init__(self) -> None:
        self._states: Dict[str, LifecycleState] = {}

    def record(self, employee_id: str, signal_type: str, now: Optional[float] = None) -> None:
        now = now if now is not None else time.time()
        multiplier, window_days = _SIGNAL_EFFECT.get(signal_type, (DEFAULT_MULTIPLIER, 0))
        self._states[employee_id] = LifecycleState(
            employee_id=employee_id,
            signal_type=signal_type,
            multiplier=multiplier,
            recorded_at=now,
            expires_at=now + window_days * 86400,
        )

    def multiplier_for(self, employee_id: str, now: Optional[float] = None) -> float:
        state = self._states.get(employee_id)
        if state is None:
            return DEFAULT_MULTIPLIER
        now = now if now is not None else time.time()
        if now >= state.expires_at:
            return DEFAULT_MULTIPLIER
        return state.multiplier

    def state_for(self, employee_id: str) -> Optional[LifecycleState]:
        return self._states.get(employee_id)


_default_store = LifecycleStore()


def get_lifecycle_store() -> LifecycleStore:
    return _default_store
