# Stores insider-threat alerts and per-employee risk snapshots in memory.
from __future__ import annotations
import itertools, time
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

# Below this, a "low" event only updates the per-user snapshot (for the
# GET /v1/insider/users/{id} detail view) but doesn't show up in the alert
# feed - that feed is meant to be the small, sustained-signal list a human
# actually triages, not every scored event.
ALERT_SEVERITY_FLOOR = "medium"
_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
MAX_ALERTS = 5000


@dataclass
class InsiderAlert:
    alert_id: int
    employee_id: str
    subtype: str
    severity: str
    risk: float
    reasons: List[str]
    timestamp: float
    # Raw feature/signal keys behind `reasons` (e.g. "new_host", "anomaly"),
    # not the formatted strings - what feedback_store.py actually damps on.
    reason_keys: List[str] = field(default_factory=list)
    feedback: Optional[str] = None  # "confirmed" | "false_positive" | None


@dataclass
class EmployeeRiskSnapshot:
    employee_id: str
    risk: float
    severity: str
    last_subtype: str
    last_reasons: List[str] = field(default_factory=list)
    # Rolling history of reasons across recent events for this subtype (see
    # risk.py's RiskState.recent_signals), not just the single most recent
    # event's reasons - a narrative built from this reads as "here's the
    # pattern over the last few days," not just "here's what just happened."
    recent_signals: List[str] = field(default_factory=list)
    last_seen: float = 0.0
    # Trailing-14-day windowed activity for this subtype only - snapshot()/
    # all_snapshots() sum this across a employee's subtypes, unlike risk
    # (which takes the max), since blast radius is genuinely additive: bytes
    # moved via file_access and via data_transfer both count.
    blast_radius_bytes: float = 0.0
    eta_critical_days: Optional[float] = None


class AlertStore:
    def __init__(self) -> None:
        self._alerts: List[InsiderAlert] = []
        self._alerts_by_id: Dict[int, InsiderAlert] = {}
        # Keyed by (employee_id, subtype) - login/file_access/data_transfer each
        # run their own independent risk tracker (they score different feature
        # spaces), so a per-employee "current risk" has to be aggregated across
        # all three, not just whichever subtype happened to send the most
        # recent event. snapshot()/all_snapshots() do that aggregation (max
        # risk across subtypes) below.
        self._subtype_snapshots: Dict[tuple, EmployeeRiskSnapshot] = {}
        self._id_counter = itertools.count(1)

    def record(
        self,
        employee_id: str,
        subtype: str,
        severity: str,
        risk: float,
        reasons: List[str],
        recent_signals: Optional[List[str]] = None,
        reason_keys: Optional[List[str]] = None,
        blast_radius_bytes: float = 0.0,
        eta_critical_days: Optional[float] = None,
    ) -> None:
        now = time.time()
        self._subtype_snapshots[(employee_id, subtype)] = EmployeeRiskSnapshot(
            employee_id=employee_id,
            risk=risk,
            severity=severity,
            last_subtype=subtype,
            last_reasons=list(reasons),
            recent_signals=list(recent_signals) if recent_signals else list(reasons),
            last_seen=now,
            blast_radius_bytes=blast_radius_bytes,
            eta_critical_days=eta_critical_days,
        )
        if _SEVERITY_RANK.get(severity, 0) >= _SEVERITY_RANK[ALERT_SEVERITY_FLOOR]:
            alert = InsiderAlert(
                alert_id=next(self._id_counter),
                employee_id=employee_id,
                subtype=subtype,
                severity=severity,
                risk=risk,
                reasons=list(reasons),
                timestamp=now,
                reason_keys=list(reason_keys) if reason_keys else [],
            )
            self._alerts.append(alert)
            self._alerts_by_id[alert.alert_id] = alert
            if len(self._alerts) > MAX_ALERTS:
                dropped = self._alerts[: len(self._alerts) - MAX_ALERTS]
                self._alerts = self._alerts[-MAX_ALERTS:]
                for old in dropped:
                    self._alerts_by_id.pop(old.alert_id, None)

    def get_alert(self, alert_id: int) -> Optional[InsiderAlert]:
        return self._alerts_by_id.get(alert_id)

    def alerts(
        self, min_severity: Optional[str] = None, employee_id: Optional[str] = None, limit: int = 200
    ) -> List[InsiderAlert]:
        items = self._alerts
        if employee_id:
            items = [a for a in items if a.employee_id == employee_id]
        if min_severity:
            floor = _SEVERITY_RANK.get(min_severity, 0)
            items = [a for a in items if _SEVERITY_RANK.get(a.severity, 0) >= floor]
        return sorted(items, key=lambda a: a.timestamp, reverse=True)[:limit]

    def _by_employee(self) -> Dict[str, List[EmployeeRiskSnapshot]]:
        by_employee: Dict[str, List[EmployeeRiskSnapshot]] = {}
        for (employee_id, _subtype), snap in self._subtype_snapshots.items():
            by_employee.setdefault(employee_id, []).append(snap)
        return by_employee

    @staticmethod
    def _merge(snaps: List[EmployeeRiskSnapshot]) -> EmployeeRiskSnapshot:
        winner = max(snaps, key=lambda s: s.risk)
        total_blast_radius = sum(s.blast_radius_bytes for s in snaps)
        return replace(winner, blast_radius_bytes=total_blast_radius)

    def snapshot(self, employee_id: str) -> Optional[EmployeeRiskSnapshot]:
        candidates = self._by_employee().get(employee_id)
        if not candidates:
            return None
        return self._merge(candidates)

    def all_snapshots(self) -> List[EmployeeRiskSnapshot]:
        combined = [self._merge(snaps) for snaps in self._by_employee().values()]
        return sorted(combined, key=lambda s: s.risk, reverse=True)


_default_store = AlertStore()


def get_alert_store() -> AlertStore:
    return _default_store
