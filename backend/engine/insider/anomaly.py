# Scores per-employee event anomalies with one HalfSpaceForest per employee/subtype.
from __future__ import annotations
from typing import Dict, List, Tuple

from backend.engine.models.classical.hst import HalfSpaceForest

from .entity_state import RunningStat

LOGIN_FEATURE_ORDER: List[str] = ["hour_zscore", "hour_drift", "new_host", "off_hours", "failed_login"]
FILE_FEATURE_ORDER: List[str] = ["volume_zscore", "volume_drift", "new_path", "off_hours", "sensitivity"]
TRANSFER_FEATURE_ORDER: List[str] = [
    "volume_zscore", "staged_trend", "transfer_drift", "new_destination", "off_hours",
]

FEATURE_ORDER: Dict[str, List[str]] = {
    "login": LOGIN_FEATURE_ORDER,
    "file_access": FILE_FEATURE_ORDER,
    "data_transfer": TRANSFER_FEATURE_ORDER,
}


# hst.py's own log-line forest (n_trees=30, height_limit=9 -> 512 leaves/tree)
# is sized for a global model fed by every log line in the process. A
# per-employee forest sees a few hundred events over an entire simulated month
# at best, so the same height leaves each leaf with under one visit on
# average - HalfSpaceForest's score is ~1/sqrt(visits), so an under-visited
# tree never stops looking "novel" no matter how normal the behavior is. Much
# shallower/narrower trees fit the actual per-entity sample size.
DEFAULT_N_TREES = 10
DEFAULT_HEIGHT_LIMIT = 3

# hour_zscore/volume_zscore/staged_trend/hour_drift are unbounded EWMA
# z-scores - left raw, a single outlier stretches the forest's per-feature
# min/max and destabilizes every threshold in the tree. HalfSpaceForest
# expects roughly [0,1]-scaled input (see log_features.py's
# log_feature_vector for the same rule applied to the log detector), so
# squash these before scoring. volume_drift/transfer_drift are ratios, not
# sigmas (see entity_state.py's drift_ratio), so they get their own divisor.
_SIGMA_FEATURES = {"hour_zscore", "hour_drift", "volume_zscore", "staged_trend"}
_RATIO_FEATURES = {"volume_drift", "transfer_drift"}
_SIGMA_SQUASH_DIVISOR = 5.0
_RATIO_SQUASH_DIVISOR = 2.0


def _squash(name: str, value: float) -> float:
    if name in _SIGMA_FEATURES:
        return min(1.0, value / _SIGMA_SQUASH_DIVISOR)
    if name in _RATIO_FEATURES:
        return min(1.0, value / _RATIO_SQUASH_DIVISOR)
    return value


class InsiderAnomalyEngine:
    """One HalfSpaceForest per (employee_id, event_subtype).

    Deliberately per-employee rather than one shared population-wide forest: the
    PS asks for a baseline "per user", and a shared model would flag anyone whose
    normal differs from the office average, not from their own history. Reuses
    backend/engine/models/classical/hst.py's HalfSpaceForest directly instead of
    a bespoke isolation-forest implementation - it's already the right primitive
    (unsupervised, online, no labels needed) and used elsewhere in RAKSHAK.
    """

    def __init__(self, n_trees: int = DEFAULT_N_TREES, height_limit: int = DEFAULT_HEIGHT_LIMIT) -> None:
        self._n_trees = n_trees
        self._height_limit = height_limit
        self._forests: Dict[Tuple[str, str], HalfSpaceForest] = {}
        # EWMA mean/variance of each employee/subtype's own raw HST scores.
        # HalfSpaceForest's raw score has a nonzero "floor" even for regular
        # behavior, and empirically that floor varies by employee and feature
        # mix rather than sitting at one universal constant - a single fixed
        # threshold on the raw score (tried first) let some employees' normal
        # floor drift close enough to the cutoff to false-trigger repeatedly.
        # Comparing the raw score to *that employee's own* recent scores,
        # like every other signal in this engine, is what actually fixes it.
        self._score_stats: Dict[Tuple[str, str], RunningStat] = {}

    def _forest_for(self, employee_id: str, subtype: str) -> HalfSpaceForest:
        key = (employee_id, subtype)
        forest = self._forests.get(key)
        if forest is None:
            forest = HalfSpaceForest(n_trees=self._n_trees, height_limit=self._height_limit)
            self._forests[key] = forest
        return forest

    def _score_stat_for(self, employee_id: str, subtype: str) -> RunningStat:
        key = (employee_id, subtype)
        stat = self._score_stats.get(key)
        if stat is None:
            stat = RunningStat()
            self._score_stats[key] = stat
        return stat

    def is_warm(self, employee_id: str, subtype: str) -> bool:
        return self._score_stat_for(employee_id, subtype).warmed_up

    def score(self, employee_id: str, subtype: str, features: Dict[str, float]) -> Tuple[float, float]:
        """Returns (raw_hst_score, self_relative_zscore). The z-score is this
        employee's current anomaly score compared to their own recent
        anomaly-score history - see the constructor docstring for why the raw
        score alone isn't a reliable absolute signal."""
        order = FEATURE_ORDER[subtype]
        vector = [_squash(name, features[name]) for name in order]
        forest = self._forest_for(employee_id, subtype)
        # score-then-update: novelty relative to history seen so far, matching
        # the same ordering hst.py's own Detector uses for log lines.
        raw_score = forest.score(vector)
        forest.update(vector)

        score_stat = self._score_stat_for(employee_id, subtype)
        self_zscore = max(0.0, score_stat.zscore(raw_score)) if score_stat.warmed_up else 0.0
        score_stat.update(raw_score)
        return raw_score, self_zscore
