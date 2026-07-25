#!/usr/bin/env python3
# Generates simulated per-employee org logs (login/file-access/data-transfer) for PS1.
#
# Writes one JSONL file per employee to <out-dir>/<employee_id>.jsonl, combining all
# three event subtypes in timestamp order - this is what scripts/agent/collector.py
# tails and forwards to the central node's /v1/insider/ingest endpoint. A minority of
# employees get a real insider pattern injected (see INSIDER_SCENARIOS below) so the
# demo has something for the baseline/anomaly engine to actually catch.
#
# Usage:
#     python samples/insider/generate_employee_logs.py [--employees 25] [--days 35]
#         [--insiders 3] [--out-dir samples/insider/logs] [--seed 42]
#
# Use at least 35 days for full 4-scenario coverage: data_transfer events only
# happen a few times a week, and the slow_drift scenario specifically needs
# ~20 of them to warm up its baseline before there's any runway left in the
# window to show a divergence. Shorter windows still work for the other three
# scenarios (resignation_exfil/staged_exfil/odd_hours_new_host).
import argparse, json, random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

DEPARTMENTS = ["engineering", "finance", "hr", "legal"]

# (path, sensitivity, department) - an employee's "normal" pool is filtered to
# their own department plus the shared public docs.
FILE_POOL: List[Tuple[str, str, str]] = [
    ("/shares/public/handbook.pdf", "public", "any"),
    ("/shares/public/org_chart.pdf", "public", "any"),
    ("/shares/engineering/design_doc.md", "internal", "engineering"),
    ("/shares/engineering/source/core.py", "internal", "engineering"),
    ("/shares/engineering/roadmap.pptx", "internal", "engineering"),
    ("/shares/engineering/oncall_runbook.md", "internal", "engineering"),
    ("/shares/finance/budget_2026.xlsx", "confidential", "finance"),
    ("/shares/finance/quarterly_report.xlsx", "confidential", "finance"),
    ("/shares/finance/payroll.csv", "restricted", "finance"),
    ("/shares/finance/vendor_invoices.csv", "internal", "finance"),
    ("/shares/hr/onboarding_guide.pdf", "public", "hr"),
    ("/shares/hr/employee_records.db", "restricted", "hr"),
    ("/shares/hr/performance_reviews.xlsx", "confidential", "hr"),
    ("/shares/legal/contracts/vendor_agreement.pdf", "confidential", "legal"),
    ("/shares/legal/nda_templates.docx", "internal", "legal"),
    ("/shares/legal/litigation_notes.docx", "restricted", "legal"),
]

NORMAL_DESTINATIONS = ["internal-fileshare", "corp-cloud-drive", "backup-nas"]
EXFIL_DESTINATIONS = ["personal-gdrive", "usb-external", "webmail-attachment"]
CHANNELS = ["network_share", "cloud_upload", "email_attachment"]
EXFIL_CHANNELS = ["usb", "cloud_upload", "email_attachment"]


@dataclass
class EmployeeProfile:
    employee_id: str
    department: str
    host_id: str
    login_hour_center: float
    normal_files: List[Tuple[str, str]]
    transfer_baseline_bytes: float
    scenario: str | None = field(default=None)


# Deterministic per-path base size so repeated access to the same file has a
# realistically tight size distribution - a wide uniform range on every access
# (e.g. randint(20_000, 900_000) regardless of file) makes even *normal*
# behavior look high-variance, which drowns out genuine anomalies in a
# baseline that's supposed to compare an employee against their own past.
def _file_base_bytes(path: str) -> float:
    tiers = {"public": 80_000, "internal": 250_000, "confidential": 500_000, "restricted": 350_000}
    sensitivity = next((s for p, s, _ in FILE_POOL if p == path), "internal")
    return float(tiers.get(sensitivity, 200_000))


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _make_profiles(n_employees: int, rng: random.Random) -> List[EmployeeProfile]:
    profiles = []
    for i in range(1, n_employees + 1):
        emp_id = f"EMP{i:03d}"
        dept = DEPARTMENTS[(i - 1) % len(DEPARTMENTS)]
        pool = [(p, s) for p, s, d in FILE_POOL if d in (dept, "any")]
        normal_files = rng.sample(pool, k=min(len(pool), rng.randint(3, 6)))
        profiles.append(
            EmployeeProfile(
                employee_id=emp_id,
                department=dept,
                host_id=f"WKS-{i:03d}",
                login_hour_center=rng.uniform(8.3, 9.6),
                normal_files=normal_files,
                transfer_baseline_bytes=rng.uniform(300_000, 900_000),
            )
        )
    return profiles


def _day_events(
    profile: EmployeeProfile, day: datetime, rng: random.Random, off_hours: bool = False, extra_sensitive: bool = False
) -> List[dict]:
    events: List[dict] = []
    hour = profile.login_hour_center + rng.gauss(0, 0.4)
    if off_hours:
        hour = rng.choice([rng.uniform(0, 5.5), rng.uniform(21, 23.9)])
    login_ts = day.replace(hour=0, minute=0, second=0) + timedelta(hours=max(0.0, hour))

    events.append(
        {
            "employee_id": profile.employee_id,
            "event_type": "login",
            "timestamp": _iso(login_ts),
            "host_id": profile.host_id,
            "src_ip": f"10.20.{int(profile.employee_id[3:]) % 250}.{rng.randint(2, 250)}",
            "success": rng.random() > 0.03,
            "method": "badge_sso",
        }
    )

    file_choices = profile.normal_files
    if extra_sensitive:
        file_choices = [(p, s) for p, s, _ in FILE_POOL if s in ("confidential", "restricted")]

    n_files = rng.randint(4, 9) if not extra_sensitive else rng.randint(8, 16)
    for _ in range(n_files):
        path, sensitivity = rng.choice(file_choices)
        ts = login_ts + timedelta(minutes=rng.uniform(5, 480))
        events.append(
            {
                "employee_id": profile.employee_id,
                "event_type": "file_access",
                "timestamp": _iso(ts),
                "host_id": profile.host_id,
                "path": path,
                "sensitivity": sensitivity,
                "action": rng.choice(["read", "read", "write", "copy"]),
                "bytes": max(1000, int(rng.gauss(_file_base_bytes(path), _file_base_bytes(path) * 0.15))),
            }
        )

    if rng.random() < 0.6:
        ts = login_ts + timedelta(minutes=rng.uniform(30, 500))
        base = profile.transfer_baseline_bytes
        events.append(
            {
                "employee_id": profile.employee_id,
                "event_type": "data_transfer",
                "timestamp": _iso(ts),
                "host_id": profile.host_id,
                "destination": rng.choice(NORMAL_DESTINATIONS),
                "channel": rng.choice(CHANNELS),
                "bytes": max(1000, int(rng.gauss(base, base * 0.2))),
            }
        )
    return events


def _apply_scenario(
    profile: EmployeeProfile, day: datetime, day_index: int, total_days: int, rng: random.Random
) -> List[dict]:
    scenario = profile.scenario
    is_weekday = day.weekday() < 5
    days_from_end = total_days - day_index

    if scenario == "resignation_exfil":
        # Quiet pre-resignation sensitive-file sweep in the final few days -
        # normal beforehand, so the baseline is genuinely "theirs" by the time
        # the anomaly shows up.
        if days_from_end <= 4 and is_weekday:
            return _day_events(profile, day, rng, off_hours=(days_from_end <= 2), extra_sensitive=True)
        return _day_events(profile, day, rng) if is_weekday else []

    if scenario == "staged_exfil":
        events = _day_events(profile, day, rng) if is_weekday else []
        if is_weekday:
            # Small, individually unremarkable transfers that climb day over
            # day - the trailing-week sum is what should catch this, not any
            # single event.
            staged_bytes = int(150_000 * (1.15 ** max(0, day_index - (total_days - 18))))
            destination = EXFIL_DESTINATIONS[0] if days_from_end <= 3 else rng.choice(NORMAL_DESTINATIONS)
            ts = day.replace(hour=int(profile.login_hour_center) + 2, minute=rng.randint(0, 59))
            events.append(
                {
                    "employee_id": profile.employee_id,
                    "event_type": "data_transfer",
                    "timestamp": _iso(ts),
                    "host_id": profile.host_id,
                    "destination": destination,
                    "channel": rng.choice(EXFIL_CHANNELS),
                    "bytes": staged_bytes,
                }
            )
        return events

    if scenario == "slow_drift":
        # No single day looks anomalous - transfer volume compounds up by
        # ~3%/weekday, well inside normal day-to-day jitter, but the recent
        # average is running well above the long-run one by the end of a
        # typical demo window. Exercises the fast-vs-slow drift features
        # specifically: a single fast EWMA baseline adapts right along with
        # this and mostly won't cross its own z-score trigger.
        #
        # A daily transfer is forced (unlike a normal day's ~60% chance) -
        # the transfer baseline needs ~20 observations to warm up at all, and
        # the point of this scenario is to test what happens once it's
        # warmed and drifting, not to also be a test of cold-start behavior.
        # Needs a window of at least ~30 days for the post-warmup runway to
        # show a clear divergence - shorter windows may under-catch it.
        if not is_weekday:
            return []
        events = [ev for ev in _day_events(profile, day, rng) if ev["event_type"] != "data_transfer"]
        growth = 1.03**day_index
        base = profile.transfer_baseline_bytes * growth
        ts = day.replace(hour=int(profile.login_hour_center) + 3, minute=rng.randint(0, 59))
        events.append(
            {
                "employee_id": profile.employee_id,
                "event_type": "data_transfer",
                "timestamp": _iso(ts),
                "host_id": profile.host_id,
                "destination": rng.choice(NORMAL_DESTINATIONS),
                "channel": rng.choice(CHANNELS),
                "bytes": max(1000, int(rng.gauss(base, base * 0.15))),
            }
        )
        return events

    if scenario == "odd_hours_new_host":
        if days_from_end <= 14 and is_weekday and rng.random() < 0.5:
            events = _day_events(profile, day, rng, off_hours=True)
            for ev in events:
                if ev["event_type"] == "login":
                    ev["host_id"] = "WKS-EXT-99"
            return events
        return _day_events(profile, day, rng) if is_weekday else []

    return _day_events(profile, day, rng) if is_weekday else ([] if rng.random() > 0.05 else _day_events(profile, day, rng))


def _hr_signal_event(employee_id: str, ts: datetime, signal_type: str) -> dict:
    return {
        "employee_id": employee_id,
        "event_type": "hr_signal",
        "timestamp": _iso(ts),
        "signal_type": signal_type,
    }


def generate(n_employees: int, days: int, n_insiders: int, seed: int) -> dict:
    rng = random.Random(seed)
    profiles = _make_profiles(n_employees, rng)
    insiders = rng.sample(profiles, k=min(n_insiders, len(profiles)))
    scenarios = ["resignation_exfil", "staged_exfil", "odd_hours_new_host", "slow_drift"]
    for i, profile in enumerate(insiders):
        profile.scenario = scenarios[i % len(scenarios)]

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    by_employee: dict = {p.employee_id: [] for p in profiles}
    for day_index in range(days + 1):
        day = start + timedelta(days=day_index)
        for profile in profiles:
            events = _apply_scenario(profile, day, day_index, days, rng)
            by_employee[profile.employee_id].extend(events)

    hr_signals: Dict[str, str] = {}

    # resignation_exfil employees get a real resignation ~6 days before their
    # sensitive-file sweep starts (which begins at days_from_end<=4) - the
    # timing a real HR system would actually produce.
    for profile in insiders:
        if profile.scenario == "resignation_exfil":
            signal_day = start + timedelta(days=max(0, days - 10))
            by_employee[profile.employee_id].append(
                _hr_signal_event(profile.employee_id, signal_day, "resignation_submitted")
            )
            hr_signals[profile.employee_id] = "resignation_submitted"

    # One employee with NO injected behavioral scenario also gets a lifecycle
    # signal and nothing else - proving the multiplier alone can't manufacture
    # an alert. It only matters when it's amplifying a real anomaly.
    clean_pool = [p for p in profiles if p.scenario is None]
    if clean_pool:
        control = rng.choice(clean_pool)
        signal_day = start + timedelta(days=max(0, days - 8))
        by_employee[control.employee_id].append(
            _hr_signal_event(control.employee_id, signal_day, "offboarding_scheduled")
        )
        hr_signals[control.employee_id] = "offboarding_scheduled (control - no anomalous behavior)"

    for events in by_employee.values():
        events.sort(key=lambda e: e["timestamp"])

    return {
        "by_employee": by_employee,
        "insiders": {p.employee_id: p.scenario for p in insiders},
        "hr_signals": hr_signals,
        "profiles": {p.employee_id: p.department for p in profiles},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--employees", type=int, default=25)
    parser.add_argument("--days", type=int, default=35)
    parser.add_argument("--insiders", type=int, default=3)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).parent / "logs")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = generate(args.employees, args.days, args.insiders, args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    total_events = 0
    for employee_id, events in result["by_employee"].items():
        path = args.out_dir / f"{employee_id}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for ev in events:
                f.write(json.dumps(ev) + "\n")
        total_events += len(events)

    manifest = {
        "employees": len(result["profiles"]),
        "days": args.days,
        "total_events": total_events,
        "insiders_ground_truth": result["insiders"],
        "hr_signals_ground_truth": result["hr_signals"],
        "note": "insiders_ground_truth/hr_signals_ground_truth are for demo narration only - "
        "the detection pipeline never sees them, it only sees the per-employee event streams.",
    }
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"wrote {total_events} events across {len(result['profiles'])} employees to {args.out_dir}")
    print(f"injected insider scenarios: {result['insiders']}")
    print(f"hr signals: {result['hr_signals']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
