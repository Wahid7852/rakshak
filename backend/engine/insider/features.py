# Extracts per-employee behavioral features relative to each employee's own baseline.
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict

from .entity_state import (
    SLOW_EWMA_ALPHA,
    TRANSFER_HISTORY_MAX_DAYS,
    EmployeeBaseline,
    drift_ratio,
    drift_zscore,
)

SENSITIVITY_WEIGHT = {"public": 0.1, "internal": 0.4, "confidential": 0.8, "restricted": 1.0}
OFF_HOURS_START, OFF_HOURS_END = 20.0, 6.0
TRANSFER_WINDOW_DAYS = 7
# "How much has actually left" over a longer window than staged_trend's 7
# days - informational (not fed into risk scoring), quantifying impact for
# an operator rather than detecting the anomaly itself.
BLAST_RADIUS_WINDOW_DAYS = 14


def _parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _hour_of_day(dt: datetime) -> float:
    return dt.hour + dt.minute / 60.0


def _is_off_hours(hour: float) -> bool:
    return hour >= OFF_HOURS_START or hour < OFF_HOURS_END


def login_features(event: Dict[str, Any], baseline: EmployeeBaseline) -> Dict[str, float]:
    dt = _parse_ts(str(event["timestamp"]))
    hour = _hour_of_day(dt)
    host = str(event.get("host_id", ""))

    hour_stat = baseline.stat("login_hour")
    hour_stat_slow = baseline.stat("login_hour:slow", alpha=SLOW_EWMA_ALPHA)
    warmed_up = hour_stat.warmed_up
    features = {
        "hour_zscore": abs(hour_stat.zscore(hour)) if warmed_up else 0.0,
        "hour_drift": abs(drift_zscore(hour_stat, hour_stat_slow)) if hour_stat_slow.warmed_up else 0.0,
        "new_host": 0.0 if (host in baseline.known_hosts or not baseline.known_hosts) else 1.0,
        "off_hours": 1.0 if _is_off_hours(hour) else 0.0,
        "failed_login": 0.0 if event.get("success", True) else 1.0,
        "warmed_up": 1.0 if warmed_up else 0.0,
    }

    hour_stat.update(hour)
    hour_stat_slow.update(hour)
    if host:
        baseline.known_hosts.add(host)
    return features


def file_access_features(event: Dict[str, Any], baseline: EmployeeBaseline) -> Dict[str, float]:
    dt = _parse_ts(str(event["timestamp"]))
    hour = _hour_of_day(dt)
    path = str(event.get("path", ""))
    sensitivity_tier = str(event.get("sensitivity", "public"))
    sensitivity = SENSITIVITY_WEIGHT.get(sensitivity_tier, 0.1)
    size_bytes = float(event.get("bytes", 0) or 0)

    # Keyed per sensitivity tier, not one blended baseline across every file
    # this employee touches - routine mixing of e.g. small public docs and
    # larger internal ones is real variance in the *file mix*, not a volume
    # anomaly, and would otherwise inflate the baseline's variance enough to
    # make ordinary access look statistically surprising.
    vol_stat = baseline.stat(f"file_bytes:{sensitivity_tier}")
    vol_stat_slow = baseline.stat(f"file_bytes:{sensitivity_tier}:slow", alpha=SLOW_EWMA_ALPHA)
    vol_warmed_up = vol_stat.warmed_up
    # Overall "have I seen enough of this employee's file activity" gate is
    # separate from the tier-specific volume stat above - a tier this employee
    # rarely touches (e.g. restricted docs, for most people) would otherwise
    # never warm up and permanently damp new_path/off_hours too, which are
    # meaningful signals on their own the moment an employee is established.
    seen_stat = baseline.stat("file_access_seen")
    warmed_up = seen_stat.warmed_up

    # Sensitivity-weighted so a restricted-tier sweep counts for more than
    # the same byte count of public docs - same weighting idea as risk.py's
    # contribution formula, applied here to an impact number instead.
    blast_radius_bytes = baseline.windowed_sum(
        "file_blast", dt.timestamp(), size_bytes * (0.5 + sensitivity), BLAST_RADIUS_WINDOW_DAYS
    )

    features = {
        "volume_zscore": max(0.0, vol_stat.zscore(size_bytes)) if vol_warmed_up else 0.0,
        "volume_drift": max(0.0, drift_ratio(vol_stat, vol_stat_slow)) if vol_stat_slow.warmed_up else 0.0,
        "new_path": 0.0 if (path in baseline.known_paths or not baseline.known_paths) else 1.0,
        "off_hours": 1.0 if _is_off_hours(hour) else 0.0,
        "sensitivity": sensitivity,
        "warmed_up": 1.0 if warmed_up else 0.0,
        "blast_radius_bytes": blast_radius_bytes,
    }

    vol_stat.update(size_bytes)
    vol_stat_slow.update(size_bytes)
    seen_stat.update(0.0)
    if path:
        baseline.known_paths.add(path)
    return features


def data_transfer_features(event: Dict[str, Any], baseline: EmployeeBaseline) -> Dict[str, float]:
    dt = _parse_ts(str(event["timestamp"]))
    hour = _hour_of_day(dt)
    ts = dt.timestamp()
    destination = str(event.get("destination", ""))
    size_bytes = float(event.get("bytes", 0) or 0)

    baseline.transfer_history.append((ts, size_bytes))
    all_cutoff = ts - TRANSFER_HISTORY_MAX_DAYS * 86400
    baseline.transfer_history[:] = [(t, b) for t, b in baseline.transfer_history if t >= all_cutoff]

    window_cutoff = ts - TRANSFER_WINDOW_DAYS * 86400
    windowed_sum = sum(b for t, b in baseline.transfer_history if t >= window_cutoff)

    vol_stat = baseline.stat("transfer_bytes")
    weekly_stat = baseline.stat("transfer_weekly_sum")
    weekly_stat_slow = baseline.stat("transfer_weekly_sum:slow", alpha=SLOW_EWMA_ALPHA)
    warmed_up = vol_stat.warmed_up
    # staged_trend catches the "small disguised increments" pattern from the PS
    # background: no single transfer looks big, but the trailing-week sum drifts
    # steadily above this employee's own historical weekly volume.
    staged_trend = max(0.0, weekly_stat.zscore(windowed_sum)) if weekly_stat.warmed_up else 0.0
    # transfer_drift is the slower-horizon version of the same idea: the
    # trailing-week sum's own fast baseline vs. its long-run baseline, for a
    # climb too gradual for staged_trend's faster window to flag on its own.
    # Ratio-based (see drift_ratio's docstring), not z-score-based - a
    # variance-normalized measure self-limits on a genuinely trending series.
    transfer_drift = (
        max(0.0, drift_ratio(weekly_stat, weekly_stat_slow)) if weekly_stat_slow.warmed_up else 0.0
    )

    blast_radius_bytes = baseline.windowed_sum("transfer_blast", ts, size_bytes, BLAST_RADIUS_WINDOW_DAYS)

    features = {
        "volume_zscore": max(0.0, vol_stat.zscore(size_bytes)) if warmed_up else 0.0,
        "staged_trend": staged_trend,
        "transfer_drift": transfer_drift,
        "new_destination": 0.0 if (destination in baseline.known_destinations or not baseline.known_destinations) else 1.0,
        "off_hours": 1.0 if _is_off_hours(hour) else 0.0,
        "warmed_up": 1.0 if warmed_up else 0.0,
        "blast_radius_bytes": blast_radius_bytes,
    }

    vol_stat.update(size_bytes)
    weekly_stat.update(windowed_sum)
    weekly_stat_slow.update(windowed_sum)
    if destination:
        baseline.known_destinations.add(destination)
    return features
