# Tracks per-employee baseline state for insider-threat behavioral scoring.
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

WARMUP_MIN_OBSERVATIONS = 20
EWMA_ALPHA = 0.05
# A slow-decaying sibling of the same quantity (~100-observation effective
# window vs. the fast stat's ~20) - see drift_zscore() below. An insider who
# drifts a little further each week can walk the fast baseline along with
# them and never cross its own z-score threshold; comparing the fast mean
# against this slower one catches that "boiling frog" pattern instead.
SLOW_EWMA_ALPHA = 0.01
TRANSFER_HISTORY_MAX_DAYS = 30


@dataclass
class RunningStat:
    """EWMA mean/variance for one numeric feature, plus a cold-start counter.

    An EWMA rather than a plain running average so a baseline can drift with an
    employee's slowly-changing normal (new project, new team) without a fixed
    training window to retrain. `warmed_up` gates scoring until there's enough
    history that a z-score actually means something - this is a chunk of the
    low-false-positive design, not just a nicety.
    """

    mean: float = 0.0
    var: float = 1.0
    n: int = 0
    alpha: float = EWMA_ALPHA

    def update(self, x: float) -> None:
        self.n += 1
        if self.n == 1:
            self.mean = x
            self.var = 1.0
            return
        diff = x - self.mean
        self.mean += self.alpha * diff
        self.var = (1 - self.alpha) * (self.var + self.alpha * diff * diff)

    def zscore(self, x: float) -> float:
        spread = max(self.var**0.5, 1e-6)
        return (x - self.mean) / spread

    @property
    def warmed_up(self) -> bool:
        return self.n >= WARMUP_MIN_OBSERVATIONS


def drift_zscore(fast: RunningStat, slow: RunningStat) -> float:
    """How far a fast (recent-weighted) baseline has wandered from its own
    slow (long-run) counterpart, in units of the slow baseline's spread.
    Only meaningful once both have enough history - callers should gate on
    `slow.warmed_up` (and typically `fast.warmed_up`) before trusting this.

    Appropriate for quantities that wander (e.g. login hour) rather than
    trend - for a genuinely climbing quantity, both EWMAs' own variance
    estimates grow right along with the climb (the update formula folds in
    each new deviation-squared), which mechanically caps how large this ratio
    can get. Use drift_ratio() instead for volume-like quantities where
    sustained growth, not wandering, is the thing being detected."""
    spread = max(slow.var**0.5, 1e-6)
    return (fast.mean - slow.mean) / spread


def drift_ratio(fast: RunningStat, slow: RunningStat) -> float:
    """How much higher the fast (recent) mean is than the slow (long-run)
    mean, as a fraction (0.5 = recent average is 50% above the long-run one).
    Not variance-normalized, so it doesn't self-limit on a trending series
    the way drift_zscore does - the right measure for "has this employee's
    recent volume climbed well past their own historical normal." Only
    meaningful once both are warmed up, same as drift_zscore."""
    return (fast.mean / max(abs(slow.mean), 1e-6)) - 1.0


@dataclass
class EmployeeBaseline:
    employee_id: str
    known_hosts: Set[str] = field(default_factory=set)
    known_paths: Set[str] = field(default_factory=set)
    known_destinations: Set[str] = field(default_factory=set)
    stats: Dict[str, RunningStat] = field(default_factory=dict)
    # (unix_ts, bytes) pairs, trimmed to TRANSFER_HISTORY_MAX_DAYS - lets the
    # transfer feature extractor compute a trailing-window sum for detecting
    # staged/incremental exfiltration, which a single-event z-score can't see.
    transfer_history: List[Tuple[float, float]] = field(default_factory=list)
    # Named trailing-value histories for windowed_sum() below, keyed
    # independently of transfer_history so callers with different window
    # lengths (e.g. blast-radius's 14 days vs. staged_trend's 7) don't collide.
    windows: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)

    def stat(self, key: str, alpha: float = EWMA_ALPHA) -> RunningStat:
        existing = self.stats.get(key)
        if existing is None:
            existing = RunningStat(alpha=alpha)
            self.stats[key] = existing
        return existing

    def windowed_sum(self, key: str, ts: float, value: float, window_days: float) -> float:
        """Appends (ts, value) to a named history and returns the sum of
        values within the trailing `window_days`. Generic version of the
        trailing-window pattern data_transfer_features built for staged_trend -
        reused here for blast-radius tracking, which needs a different
        window length on a different (but similarly-shaped) history."""
        history = self.windows.setdefault(key, [])
        history.append((ts, value))
        trim_cutoff = ts - window_days * 3 * 86400
        history[:] = [(t, v) for t, v in history if t >= trim_cutoff]
        cutoff = ts - window_days * 86400
        return sum(v for t, v in history if t >= cutoff)


class EntityBaselineStore:
    """In-memory per-employee baseline registry, created lazily on first event."""

    def __init__(self) -> None:
        self._employees: Dict[str, EmployeeBaseline] = {}

    def get(self, employee_id: str) -> EmployeeBaseline:
        emp = self._employees.get(employee_id)
        if emp is None:
            emp = EmployeeBaseline(employee_id=employee_id)
            self._employees[employee_id] = emp
        return emp

    def all(self) -> Dict[str, EmployeeBaseline]:
        return self._employees
