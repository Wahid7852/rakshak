# RAKSHAK: Autonomous Threat Hunter for Insider Attacks

Team: Garima Shrivastava, Abdul Wahid Khan, Anna Mariya Martin

## The problem

Insider threats don't look like attacks until the damage is done. An employee quietly
pulling sensitive files before resigning, or moving data out in small disguised increments,
looks like normal activity to any rule-based system. There's no labeled dataset of "insider
attacks" to train a classifier on, and a flat threshold either fires on everyone whose job
involves bulk access or misses the quiet, gradual case entirely.

## What RAKSHAK does

One central node ingests login, file-access, and data-transfer events from lightweight
collector agents on each monitored machine. Not one RAKSHAK per employee, one RAKSHAK
watching the whole fleet.

- Builds a behavioral baseline per employee, from their own history, not an office-wide rule
- Scores new events against that baseline with an unsupervised anomaly engine, no labeled
  training data required
- Surfaces alerts with a severity score and a plain-language reason
- Designed around one rule: no single anomalous event should ever reach high severity alone

## Low false positives, the actual mechanism

- Every signal (unusual login hour, new host, new file path, off-hours activity, volume
  spikes, a trailing 7-day transfer trend) triggers only past a real statistical threshold
- Risk decays with a 3-day half-life, a one-off event fades back out on its own
- Severity only escalates on sustained or corroborating signal, several distinct anomalies
  close together, not one event in isolation

## Beyond the brief

Five things the problem statement didn't ask for, built anyway:

- **Dual-timescale baseline** - a fast and a slow baseline running side by side catch an
  employee who drifts a little further each week, gradually enough to fool a single
  adaptive baseline
- **HR signal fusion** - a resignation or PIP flag raises scrutiny, but only ever amplifies
  a real anomaly, never triggers an alert by itself
- **Plain-language narrative** - every alert reads as a paragraph explaining what happened,
  not just a number
- **Analyst feedback loop** - confirm or dismiss an alert and the system adjusts that
  specific signal's weight for that specific employee going forward
- **Blast-radius and time-to-critical** - how much sensitive activity moved in the last two
  weeks, and a projected days-to-critical at the current rate

## Results

Validated across multiple independently-seeded simulated runs (12-20 employees, 25-35 days,
3-5 injected insider scenarios per run, none of it visible to the detection pipeline). Most
recent clean run: 3 for 3 injected insiders flagged critical, all 9 normal employees stayed
low, including one employee carrying only an HR lifecycle signal and no anomalous behavior
at all.

## Engineering

- 239 tests passing, 76 of them purpose-built for the insider-threat engine
- 80% test coverage against a 76% CI floor
- Style, lint, type-check, and security scans all clean on every changed file
- Fully Windows-compatible collector agent: pure standard library, no OS-specific APIs,
  same file-tail-then-forward design on Windows or Linux

## What's next

- Real Windows Event Log / USN-journal collection (currently simulated org data, which is
  what the brief actually asks for)
- Baseline persistence across a restart
- Cross-employee correlation for coordinated activity
- A native desktop view alongside the current web dashboard
