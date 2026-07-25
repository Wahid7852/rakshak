# Wires per-employee baselining, anomaly scoring, and risk into orchestrator detectors.
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Literal, Tuple

from backend.orchestrator.types import Decision

from .alert_store import get_alert_store
from .anomaly import InsiderAnomalyEngine
from .entity_state import EntityBaselineStore
from .feedback_store import get_feedback_store
from .features import data_transfer_features, file_access_features, login_features
from .lifecycle_store import DEFAULT_MULTIPLIER, get_lifecycle_store
from .risk import RiskTracker, eta_critical_days

_FEATURE_FUNCS = {
    "login": login_features,
    "file_access": file_access_features,
    "data_transfer": data_transfer_features,
}


def _parse_event_time(event: Dict[str, Any]) -> float | None:
    raw = event.get("timestamp")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None

# Binary flags trigger at >=1.0; z-score-shaped features trigger past a
# threshold in standard deviations (see _ZSCORE_TRIGGER/_DRIFT_TRIGGER below).
# Weights are capped and modest on purpose - see risk.py's docstring on why no
# single event should be able to reach "high" alone.
_FLAG_WEIGHT = {
    "hour_zscore": 0.12,
    "hour_drift": 0.10,
    "new_host": 0.10,
    "failed_login": 0.08,
    "volume_zscore": 0.10,
    "volume_drift": 0.10,
    "new_path": 0.06,
    "new_destination": 0.12,
    "staged_trend": 0.20,
    "transfer_drift": 0.10,
    "off_hours": 0.06,
}
_BINARY_FLAGS = {"new_host", "new_path", "new_destination", "failed_login", "off_hours"}
# hour_drift stays sigma-shaped (login hour wanders, it doesn't trend) - a
# softer trigger than a raw z-score is appropriate since it's comparing two
# already-smoothed quantities, which have less raw noise to begin with.
_SIGMA_DRIFT_TRIGGER = 1.5
# volume_drift/transfer_drift are ratios (recent-average / long-run-average -
# 1), not sigmas - see entity_state.py's drift_ratio docstring for why a
# variance-normalized measure self-limits on a genuinely climbing series.
# 0.4 means this employee's recent average is running 40%+ above their own
# long-run one.
_RATIO_DRIFT_TRIGGER = 0.4
# 2.5 sigma rather than 2.0 - at 2.0, a purely normal Gaussian process trips
# this "anomalous" ~2.3% of the time per event, which adds up to several
# false triggers per employee over a month of daily activity. 2.5 sigma
# (~0.6% per event) keeps the same detector meaningfully rarer by chance.
_ZSCORE_TRIGGER = 2.5
_COLD_START_DAMPING = 0.3  # flag-only contribution while the HST/baseline is still warming up

# The anomaly signal triggers on a z-score of the employee's *own* recent raw
# HST scores (see anomaly.py's InsiderAnomalyEngine), not a fixed cutoff on
# the raw score - empirically, that raw-score "floor" varies enough by
# employee/feature-mix that a single global threshold let some employees
# false-trigger repeatedly. A higher trigger and lower weight than the other
# z-score signals: raw HST scores are bounded in [0,1] and often skewed
# toward their floor rather than roughly Gaussian, so a "2.5 sigma" cutoff
# computed from mean/variance doesn't land at the same real rarity a
# genuinely Gaussian quantity would - 3.0 with a smaller bonus keeps this
# signal net-positive without letting it dominate on its own over a long
# window.
_ANOMALY_TRIGGER = 3.0
_ANOMALY_BONUS = 0.14

_REASON_TEMPLATES = {
    "hour_zscore": "login at an unusual hour for this employee ({value:.1f} sigma from their baseline)",
    "hour_drift": "login-time pattern has gradually drifted from this employee's long-run normal ({value:.1f} sigma)",
    "new_host": "login from a host not seen before for this employee",
    "failed_login": "failed login attempt",
    "volume_zscore": "access/transfer volume far above this employee's own baseline ({value:.1f} sigma)",
    "volume_drift": "file access volume has climbed {value:.0%} above this employee's long-run normal",
    "new_path": "access to a file path not seen before for this employee",
    "new_destination": "transfer to a destination not seen before for this employee",
    "staged_trend": "trailing 7-day transfer volume trending well above this employee's normal ({value:.1f} sigma)",
    "transfer_drift": "transfer volume has climbed {value:.0%} above this employee's long-run normal, beyond the 7-day trend alone",
    "off_hours": "activity outside normal working hours",
}

# (trigger, scale_denominator) per non-binary feature - scale_denominator is
# the value at which a fully-triggered feature contributes its full weight
# (scale caps at 1.0 beyond that), sized to each feature's actual value range.
_THRESHOLDS: Dict[str, Tuple[float, float]] = {
    "hour_zscore": (_ZSCORE_TRIGGER, 4.0),
    "volume_zscore": (_ZSCORE_TRIGGER, 4.0),
    "staged_trend": (_ZSCORE_TRIGGER, 4.0),
    "hour_drift": (_SIGMA_DRIFT_TRIGGER, 4.0),
    "volume_drift": (_RATIO_DRIFT_TRIGGER, 1.5),
    "transfer_drift": (_RATIO_DRIFT_TRIGGER, 1.5),
}


# A z-score-shaped feature that's "elevated" (past this fraction of its own
# trigger) but hasn't fully crossed it earns no credit on its own - one
# elevated-but-sub-threshold reading is unremarkable noise. But several of
# them elevated *in the same event* is a real, rarer-by-chance correlation
# (independently ~13% each at this fraction, so multiple together is a lot
# less likely than any one alone) - a legitimate case for partial credit that
# doesn't reopen the single-weak-signal-compounds-over-time failure mode this
# engine hit twice already (see anomaly.py/risk.py docstrings).
_ELEVATED_FRACTION = 0.6
_ELEVATED_WEIGHT_SCALE = 0.3
_ELEVATED_MIN_COUNT = 2


def _reasons_and_contribution(employee_id: str, features: Dict[str, float]) -> Tuple[List[str], float, List[str]]:
    reasons: List[str] = []
    contribution = 0.0
    triggered_keys: List[str] = []
    elevated: List[Tuple[str, float, float]] = []  # (key, value, trigger)
    feedback = get_feedback_store()

    for key, weight in _FLAG_WEIGHT.items():
        value = features.get(key)
        if value is None:
            continue
        damping = feedback.multiplier_for(employee_id, key)
        if key in _BINARY_FLAGS:
            if value >= 1.0:
                reasons.append(_REASON_TEMPLATES[key].format(value=value))
                contribution += weight * damping
                triggered_keys.append(key)
            continue

        trigger, scale_denominator = _THRESHOLDS[key]
        if value >= trigger:
            reasons.append(_REASON_TEMPLATES[key].format(value=value))
            contribution += weight * min(1.0, value / scale_denominator) * damping
            triggered_keys.append(key)
        elif value >= trigger * _ELEVATED_FRACTION:
            elevated.append((key, value, trigger))

    if len(elevated) >= _ELEVATED_MIN_COUNT:
        for key, value, trigger in elevated:
            damping = feedback.multiplier_for(employee_id, key)
            contribution += _FLAG_WEIGHT[key] * _ELEVATED_WEIGHT_SCALE * min(1.0, value / trigger) * damping
            triggered_keys.append(key)
        names = ", ".join(key.replace("_", " ") for key, _v, _t in elevated)
        reasons.append(
            f"multiple signals simultaneously elevated without any one fully triggering ({names})"
        )

    return reasons, contribution, triggered_keys


class InsiderDetector:
    """One instance per event subtype (login / file_access / data_transfer).

    Holds baseline + anomaly + risk state for every employee it has seen, the
    same way the log_hst detector keeps its forest state in-process across
    requests - state here is what makes "per user" baselining possible at all.
    """

    def __init__(self, subtype: str, name: str) -> None:
        self.subtype = subtype
        self.name = name
        self.cost_ms_estimate = 2
        self._baselines = EntityBaselineStore()
        self._anomaly = InsiderAnomalyEngine()
        self._risk = RiskTracker()

    async def score(self, payload: Any, context: Any) -> Decision:
        event: Dict[str, Any] = payload if isinstance(payload, dict) else {}
        employee_id = str(event.get("employee_id", "unknown"))

        baseline = self._baselines.get(employee_id)
        feature_fn = _FEATURE_FUNCS[self.subtype]
        features = feature_fn(event, baseline)

        raw_anomaly_score, anomaly_zscore = self._anomaly.score(employee_id, self.subtype, features)
        reasons, flag_contribution, triggered_keys = _reasons_and_contribution(employee_id, features)

        warmed_up = features.get("warmed_up", 0.0) >= 1.0
        anomaly_warm = self._anomaly.is_warm(employee_id, self.subtype)
        if warmed_up and anomaly_warm and anomaly_zscore >= _ANOMALY_TRIGGER:
            anomaly_damping = get_feedback_store().multiplier_for(employee_id, "anomaly")
            reasons = reasons + [
                f"shape of this event is unusually novel even by this employee's own recent standard "
                f"(HST score {raw_anomaly_score:.2f}, {anomaly_zscore:.1f} sigma above their typical score)"
            ]
            flag_contribution += _ANOMALY_BONUS * anomaly_damping
            triggered_keys.append("anomaly")

        contribution = flag_contribution if warmed_up else flag_contribution * _COLD_START_DAMPING

        # A departing/PIP employee isn't inherently guilty - the lifecycle
        # multiplier only matters when it's amplifying a real contribution,
        # never an isolated trigger of its own (see lifecycle_store.py).
        lifecycle_multiplier = get_lifecycle_store().multiplier_for(employee_id)
        if lifecycle_multiplier > DEFAULT_MULTIPLIER and contribution > 0.0:
            contribution *= lifecycle_multiplier
            reasons = reasons + ["elevated scrutiny: employee is in a departing/offboarding or PIP window"]

        event_time = _parse_event_time(event)
        state = self._risk.update(employee_id, contribution, reasons, event_time=event_time)
        severity = self._risk.severity_for(state.risk)
        get_alert_store().record(
            employee_id,
            self.subtype,
            severity,
            state.risk,
            reasons,
            recent_signals=state.recent_signals,
            reason_keys=triggered_keys,
            blast_radius_bytes=features.get("blast_radius_bytes", 0.0),
            eta_critical_days=eta_critical_days(state),
        )

        verdict: Literal["malicious", "benign"] = "malicious" if severity in ("high", "critical") else "benign"
        confidence = 1.0 if warmed_up else 0.3
        return Decision(state.risk, confidence, verdict, self.name)


class InsiderHrSignalDetector:
    """Handles hr_signal events: records lifecycle state for
    InsiderDetector's other three instances to read, no baseline/anomaly
    scoring of its own - a resignation or PIP isn't itself an anomaly, it's
    context that changes how much an anomaly elsewhere should matter."""

    name = "insider_hr_signal"
    cost_ms_estimate = 1

    async def score(self, payload: Any, context: Any) -> Decision:
        event: Dict[str, Any] = payload if isinstance(payload, dict) else {}
        employee_id = str(event.get("employee_id", "unknown"))
        signal_type = str(event.get("signal_type", ""))
        get_lifecycle_store().record(employee_id, signal_type)
        return Decision(0.0, 0.0, "unknown", self.name)
