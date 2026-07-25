# Solution overview

**RAKSHAK** is a central threat-hunting node that ingests login, file-access, and
data-transfer events from thin collector agents running on monitored machines, builds a
behavioral baseline per employee, and scores each new event against *that employee's own
history* - not a population-wide rule - to surface insider-threat alerts with a severity
score and a plain-language reason.

Beyond what the PS literally asks for, RAKSHAK also: resists an insider who drifts slowly
enough to fool a single adaptive baseline; fuses a fourth, deliberately out-of-PS signal type
(HR/lifecycle events) to catch the PS's own named "before resignation" scenario more directly
than login/file/transfer logs alone can; explains every alert in a plain-language paragraph
instead of a bare score; gets better with light analyst feedback without ever needing labeled
training data; and quantifies both how much has actually left and how urgent the situation is.
See "Beyond the PS" below for what each of these actually does and why.

This is a pivot of the existing RAKSHAK codebase (previously built for a different assigned
theme, quantum-assisted malware/log detection) onto Problem Statement 1. The reusable parts
of that system - a decision orchestrator, a detector registry, an HTTP+gRPC API layer, and
an existing unsupervised online anomaly model - carry over directly; everything about *what*
gets modeled and *how false positives are controlled* is new, built for this PS specifically.
The prior malware/network-flow detectors (`file_ml_or_rf`, `file_qsvc`, the EMBER/UNSW
pipelines) are untouched and unrelated to this feature - they stay in the repo but aren't
part of this pitch.

## What the theme asked for, and what RAKSHAK ships

| Theme ask | RAKSHAK today |
|---|---|
| Ingest simulated organizational logs (login, file access, data transfers), per employee | `samples/insider/generate_employee_logs.py` generates per-employee login/file-access/data-transfer JSONL streams with realistic normal behavior, plus a minority of employees carrying real insider patterns (see below). `scripts/agent/collector.py` is the collector agent that would run on each real machine, tailing its local event log and forwarding batches to the central node - the same file-tail-then-POST shape works unmodified on Windows or Linux. |
| One central system, not one instance per employee | A single RAKSHAK backend (`backend/api/main.py`) receives all events at `POST /v1/insider/ingest`. Nothing runs on the monitored machine except the lightweight collector - no detection logic, no model, no per-machine state. |
| Behavioral baseline per user/entity | `backend/engine/insider/entity_state.py` keeps one baseline per `employee_id`: EWMA mean/variance per numeric feature, plus known-hosts/known-paths/known-destinations sets, gated by a warm-up period (~20 observations) before it's trusted enough to score against. |
| Anomaly detection engine, not purely rule-based | Two signals combine: (1) explainable statistical flags - z-score deviation from the employee's own EWMA baseline, novelty of host/path/destination, off-hours activity, a trailing-7-day transfer-volume trend for catching staged/incremental exfiltration; (2) an unsupervised `HalfSpaceForest` (reused directly from `backend/engine/models/classical/hst.py`, RAKSHAK's existing online anomaly forest) scoring the shape of each event against that employee's own event history, one forest per (employee, event type). Neither signal needs a single labeled insider-attack example. |
| Alert dashboard with severity scoring | `backend/api/static/insider_dashboard.html`, served at `/insider/dashboard`: a severity-sorted alert feed with plain-language reasons ("login from a host not seen before for this employee", "trailing 7-day transfer volume trending well above this employee's normal") and a per-employee risk panel. Backed by `GET /v1/insider/alerts` and `GET /v1/insider/users/{employee_id}`. |
| Low false-positive design philosophy | Explained in detail below - the short version is that no single anomalous event can reach a high severity alone, and severity only escalates when deviation is sustained or corroborated by more than one signal. |

## The low-false-positive mechanism, specifically

This is the part of the PS that's easy to state and easy to get wrong, so it's worth being
precise about the actual mechanism (`backend/engine/insider/risk.py`, `pipeline.py`):

- Every event contributes a small, capped amount of "risk" to that employee, only when a
  statistical threshold is actually crossed (2.5 standard deviations from their own
  baseline, or a genuinely new host/path/destination) - not a continuous score that drifts
  upward regardless of behavior.
- Risk decays with a 3-day half-life. A single off-hours login or one large file read fades
  back out on its own if nothing else follows it.
- Severity buckets (`low` / `medium` / `high` / `critical`) require *accumulated or
  corroborating* signal to climb: `critical` in practice means several distinct anomalies
  across a short window, not one event.
- The unsupervised `HalfSpaceForest` signal is threshold-gated the same way, not
  continuously weighted in - we found by testing that any small continuous per-event
  contribution compounds past any threshold within a single day purely from event volume,
  regardless of whether behavior is actually unusual. Gating it like the statistical flags
  fixed that.
- File-access volume baselines are kept per sensitivity tier (public/internal/confidential/
  restricted) rather than one blended number - an employee who routinely reads both small
  public docs and larger internal ones isn't inherently "high variance," and blending those
  into one baseline was inflating false positives in testing.

Measured on independently-seeded simulated runs (12-16 employees, 25-35 days, 3-4 injected
insider scenarios per run): every injected insider scenario was correctly flagged medium
severity or higher, and normal employees stayed low in the common case. One stress run (16
employees/42 days) surfaced a real calibration bug - a fixed threshold on the raw anomaly
score didn't generalize across employees - documented and fixed below, in
`technical-approach.md`, and is the reason the self-relative anomaly z-score exists at all.
That's a small demo-scale evaluation, not a rigorous benchmark - stated honestly rather than
oversold.

## Simulated insider scenarios

`generate_employee_logs.py` injects patterns straight from the PS background, plus one that
specifically exercises the dual-timescale baseline below:

- **`resignation_exfil`** - a quiet shift to sensitive-file access in the final days of the
  window, files well outside the employee's normal working set. Paired with a real
  `resignation_submitted` HR signal ~6 days earlier, matching real-world timing.
- **`staged_exfil`** - data-transfer volume that climbs day over day in small increments,
  each individually unremarkable, caught by the trailing-7-day-sum feature rather than any
  single transfer.
- **`odd_hours_new_host`** - intermittent off-hours logins from a host never seen before for
  that employee.
- **`slow_drift`** - transfer volume that compounds up by a few percent every weekday, well
  inside normal day-to-day jitter, ending up well above where it started. No single day looks
  anomalous; only the fast-vs-slow baseline comparison catches it.

One additional employee gets an HR signal (`offboarding_scheduled`) with **no** anomalous
behavior at all, specifically to demonstrate the lifecycle multiplier doesn't manufacture an
alert on its own - a resignation isn't guilt, it only amplifies a real signal that's already
there.

## Beyond the PS: five extraordinary enhancements

The PS asks for per-user baselining, anomaly detection, a severity dashboard, and low false
positives. RAKSHAK does all four - and also does the following, none of which the PS asked
for, all of which make the detector harder to fool or its output more useful to an operator.

**1. Dual-timescale baseline (resists slow-drift evasion).** Every EWMA baseline so far was
a single fast one (~20-observation effective window) - an insider who drifts a little further
each week can walk that baseline along with them and never cross its own z-score threshold.
`entity_state.py`'s `RunningStat` now takes a configurable `alpha`, and the three volume/
timing-heavy features (login hour, file-access volume per tier, transfer weekly-sum) each
maintain a slow-decaying sibling (`SLOW_EWMA_ALPHA`). `drift_ratio()`/`drift_zscore()`
compare the fast mean against the slow one - this is the literal technical answer to the PS's
own "small, disguised increments" language, applied to gradual drift instead of just abrupt
staged transfers.

**2. HR/lifecycle signal fusion.** A fourth event type, `hr_signal`
(`resignation_submitted` / `offboarding_scheduled` / `performance_improvement_plan` /
`role_change`), deliberately outside the three log types the PS lists - nothing in login/
file/transfer data says *why* behavior changed. `lifecycle_store.py` tracks a time-boxed risk
multiplier per employee (1.75x for 45 days on a resignation/offboarding, 1.3x for 30 days on
a PIP) that amplifies an *existing* contribution, never fires alone. This directly attacks
the PS's flagship scenario using a signal the PS didn't ask for.

**3. Plain-language incident narrative.** `narrative.py` composes a grounded paragraph per
employee from the real reason strings and numbers already computed elsewhere in the engine -
no invented detail, no LLM/cloud call. Shown on the dashboard under each medium+ employee.

**4. Analyst feedback loop.** `POST /v1/insider/alerts/{id}/feedback` with
`confirmed`/`false_positive`. A dismissal halves that specific reason's weight for that
specific employee going forward (floor at 15%, never fully silenced); a confirmation resets
it. Still fundamentally unsupervised at cold start - this is how it gets better *after* cold
start, without ever needing labeled training data.

**5. Blast-radius + time-to-critical.** `GET /v1/insider/users/{id}` also returns
`blast_radius_bytes` (trailing-14-day sensitivity-weighted activity, summed across
file-access and data-transfer) and `eta_critical_days` (projected days to critical at the
current contribution rate, using each event's own declared timestamp so a demo backfilling a
month of history in seconds doesn't produce a nonsensical rate). Both feed the narrative for
a stronger sentence: *"~35.2MB of activity in the trailing 14 days; projected to reach
critical in ~2.1 day(s) at the current rate."*

## What's honestly not built yet

- Real Windows Event Log / USN-journal collection. The collector agent's file-tail-then-POST
  design is genuinely Windows-compatible today, but pulling from the real Security event log
  (4624/4625) or NTFS journal is a documented next step, not implemented for this pitch -
  the PS explicitly asks for *simulated* organizational logs, which is what's wired up.
- Baseline persistence across a backend restart. Baselines currently live in process memory
  (the same pattern the existing `log_hst`/`log_ngram` detectors use for their own state,
  minus the periodic checkpoint they have); a restart starts every employee's baseline cold.
- A Qt desktop view for these alerts. The severity dashboard is a web page for now,
  deliberately - iterating on it doesn't require a C++/CMake rebuild cycle. Folding it into
  `client-qt` alongside the existing Dashboard/Audit Logs pages is a reasonable next step,
  not done here.
- Cross-employee correlation. Every baseline here is strictly per-individual, which is what
  the PS asked for - detecting a *coordinated* pattern (several employees touching the same
  sensitive resource in a short window) is a natural extension, not built.
- A real HR system integration for lifecycle signals. `hr_signal` events are ingested exactly
  like the other three types and the multiplier logic is real, but there's no connector to an
  actual HRIS - `generate_employee_logs.py` injects them the same way it injects everything
  else, for the same "simulated organizational data" reason the PS scopes to.
