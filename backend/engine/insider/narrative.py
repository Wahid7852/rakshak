# Composes a plain-language incident summary from an employee's real scored signals.
from __future__ import annotations
from typing import List, Optional

_SEVERITY_LEAD = {
    "critical": "{employee_id} is at critical risk (score {risk:.2f}), driven by {subtype} activity.",
    "high": "{employee_id} is at high risk (score {risk:.2f}), driven by {subtype} activity.",
    "medium": "{employee_id} is at medium risk (score {risk:.2f}) and worth a look, most recently via {subtype} activity.",
    "low": "{employee_id} shows no significant behavioral deviation (score {risk:.2f}, {subtype} activity).",
}
_SUBTYPE_LABEL = {"login": "login", "file_access": "file access", "data_transfer": "data transfer"}
_BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"]


def _human_bytes(n: float) -> str:
    for unit in _BYTE_UNITS:
        if n < 1024.0:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def build_narrative(
    employee_id: str,
    severity: str,
    risk: float,
    subtype: str,
    recent_signals: List[str],
    blast_radius_bytes: float = 0.0,
    eta_critical_days: Optional[float] = None,
) -> str:
    """Grounds strictly in the real reason strings and numbers already
    computed elsewhere in this engine (pipeline.py's _REASON_TEMPLATES,
    risk.py's RiskState.recent_signals/eta_critical_days,
    features.py's blast_radius_bytes) - no invented detail. A severity/
    score/subtype lead sentence, plus what was actually observed for
    medium+ employees so there's something to act on, not just a number."""
    subtype_label = _SUBTYPE_LABEL.get(subtype, subtype)
    lead = _SEVERITY_LEAD.get(severity, _SEVERITY_LEAD["low"]).format(
        employee_id=employee_id, risk=risk, subtype=subtype_label
    )

    if severity == "low":
        return lead

    parts = [lead]

    observations = _dedupe_preserve_order(recent_signals)
    if observations:
        parts.append("Recent signals: " + "; ".join(observations) + ".")

    impact = []
    if blast_radius_bytes > 0:
        impact.append(f"~{_human_bytes(blast_radius_bytes)} of activity in the trailing 14 days")
    if eta_critical_days is not None:
        impact.append(f"projected to reach critical in ~{eta_critical_days:.1f} day(s) at the current rate")
    if impact:
        sentence = "; ".join(impact) + "."
        parts.append(sentence[0].upper() + sentence[1:])

    return " ".join(parts)
