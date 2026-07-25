# Solution overview

**RAKSHAK** is a local-first, hybrid classical+quantum threat detection system: a
cascading decision engine (FastAPI + gRPC backend) fronted by a Qt6 desktop console. It
answers the assigned theme directly, point by point.

## What the theme asked for, and what RAKSHAK ships

| Theme ask | RAKSHAK today |
|---|---|
| Hybrid AI system (classical + quantum) | `file_qsvc` — a PennyLane quantum-embedded SVM — is fused with classical detectors through confidence-weighted averaging. It's a real cascade stage, not a bolted-on quantum demo running on the side. |
| Detect unknown malware patterns | `log_hst` and `log_ngram` are unsupervised, online detectors — they calibrate live with no labeled training set, so they flag genuinely novel behavior instead of only matching known signatures. `file_static` and `file_ml_or_rf` score files on learned structural/byte features, so a never-before-seen binary with malicious characteristics still gets caught. |
| Predict ransomware deployment patterns from user behavior logs | The log cascade scores arbitrary log lines/streams for anomalies in real time — auth failures, unusual bursts, the kind of behavior that precedes a ransomware payload. This is the right *primitive* for early ransomware-behavior detection, and it's built and working today. Stated honestly: there is no ransomware-labeled training set or ransomware-specific classifier in the repo yet — this is the general-purpose anomaly engine the theme needs, positioned for that use case, not a shipped ransomware detector. |
| Real-time | The cascade runs on a latency budget (5ms p95 for log events, 50ms for an initial file verdict, 250ms total including sandbox enrichment) specifically so cheap detectors resolve the vast majority of events immediately, and the expensive quantum stage only runs on genuinely borderline cases. |
| Dataset: simulated network traffic or malware signatures | RAKSHAK trains on real data instead: LogHub HDFS_v1 (real distributed-system logs) and EMBER2018 (a real malware PE feature corpus) — a deliberate upgrade over the suggested simulated baseline. |

## The product layer

On top of the detection engine, a Qt6 desktop console gives an operator:

- A live dashboard with real cumulative counters (files scanned, lines checked, monitoring
  uptime) — not decorative placeholders.
- On-demand file scan and log-line checking, both wired to the real backend.
- Continuous background log tailing with a raw-tail view and a flagged-lines table.
- Encrypted quarantine (Fernet + HMAC-signed) with list/restore/delete.
- An adjustable UI (resizable columns, resizable sidebar, both persisted) and a live
  light/dark theme toggle.

## Why the honesty angle is itself a differentiator

The project documents its own weak points instead of overselling them: the quantum
tie-breaker's AUC is openly called "modest" (0.69) in its own results doc, the log
anomaly model's precision/recall tradeoff is explained rather than hidden, and this pitch
says plainly that ransomware-specific labeled training hasn't happened yet. For a security
tool, that kind of self-reported honesty is a trust signal, not a weakness to paper over.
