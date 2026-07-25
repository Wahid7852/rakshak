# Tracks analyst feedback (confirmed/false_positive) as a per-employee, per-reason damping multiplier.
from __future__ import annotations
from typing import Dict, List, Tuple

# A dismissal halves that specific reason's weight for that specific employee
# going forward - never to zero (FLOOR), so a real recurrence still shows up,
# just weighted down. This is the "gets better with light human supervision,
# without ever needing labeled training data up front" mechanism: still
# fundamentally unsupervised at cold start, self-tuning per employee/reason
# once an analyst has looked at it once.
FALSE_POSITIVE_DECAY = 0.5
FLOOR_MULTIPLIER = 0.15
DEFAULT_MULTIPLIER = 1.0


class FeedbackStore:
    def __init__(self) -> None:
        self._multipliers: Dict[Tuple[str, str], float] = {}

    def multiplier_for(self, employee_id: str, reason_key: str) -> float:
        return self._multipliers.get((employee_id, reason_key), DEFAULT_MULTIPLIER)

    def apply(self, employee_id: str, reason_keys: List[str], verdict: str) -> None:
        for key in reason_keys:
            entry = (employee_id, key)
            if verdict == "false_positive":
                current = self._multipliers.get(entry, DEFAULT_MULTIPLIER)
                self._multipliers[entry] = max(FLOOR_MULTIPLIER, current * FALSE_POSITIVE_DECAY)
            elif verdict == "confirmed":
                # an analyst confirming a hit shouldn't leave stale damping
                # from an earlier, unrelated dismissal of the same reason type
                self._multipliers[entry] = DEFAULT_MULTIPLIER


_default_store = FeedbackStore()


def get_feedback_store() -> FeedbackStore:
    return _default_store
