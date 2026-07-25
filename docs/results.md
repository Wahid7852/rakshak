# Results

Real, measured numbers for the detectors behind `backend/orchestrator/registry.py`.
Previous version of this doc described a different, unimplemented pipeline
(encrypted-file/TLS-simulation) - see `docs/overview.md`, which still
documents that separate vision. This doc covers what's actually live.

Training scripts: `scripts/dev/train_log_sgd.py`, `scripts/dev/train_file_rf.py`,
`scripts/dev/train_qsvc.py`. Rerun any of them to reproduce/update these numbers.

## Log detectors (`log_hst`, `log_ngram`, `log_sgd`)

`backend/engine/models/classical/{hst,ngram,sgd}.py`, fed by
`backend/engine/features/log_features.py`.

`log_hst` (streaming Half-Space Trees) and `log_ngram` (online Markov n-gram)
are unsupervised - no training set, they calibrate from traffic they see.
No offline metric to report for those two; sanity-tested manually against a
mix of routine and injection-style lines (see commit history / session
transcript) and confirmed real, varying, non-constant scores.

`log_sgd` is supervised, pretrained on LogHub's HDFS_v1 (real block-level
anomaly labels):

```
accuracy:  0.9953
precision: 0.2696
recall:    0.6610
auc:       0.9823
n_train:   2755 (class-balanced sample)
n_test:    80000 (natural distribution)
```

**Caveat on precision**: HDFS_v1's ground truth is block-level (a whole
block of ~20 log lines is labeled Anomaly/Success as a unit), but `log_sgd`
scores one line at a time. Line labels here are derived from which of
HDFS_v1's 29 known event templates a line matches, weighted by that
template's real corpus-level anomaly association (lift ≥ 5x base rate) -
this is a much better signal than naively propagating the block label to
every line (that approach measured AUC ~0.54, barely above chance). Low
precision on the natural-distribution test set reflects a genuinely rare
target (0.23% positive rate), not a broken model - a block-level rollup
check (any line in the block scores ≥0.5) gets 90.5% recall / 18.6%
precision on held-out blocks, i.e. it reliably flags real anomalous blocks
at the cost of over-alerting, which is the right failure mode for an
early-cascade "nudge" signal that other detectors get to overrule.

## File detector (`file_ml_or_rf`)

`backend/engine/models/classical/file_rf.py`, feature extraction via
`backend/engine/models/pe_features.py` (vendored from `elastic/ember`,
feature_version=2, 2381-dim). Trained on EMBER2018 (HF mirror
`cw1521/ember2018-malware`), 80,000 train / 15,000 test rows, class-balanced.

```
                accuracy  precision  recall   auc
LightGBM (used) 0.9491    0.9390     0.9616   0.9891
RandomForest     0.9099    0.8884     0.9395   0.9721
```

LightGBM was selected (higher AUC). Only scores payloads with an `MZ`
header (PE files) - returns "unknown" (neutral, zero confidence) for
anything else rather than guessing at a format it was never trained on.

**Known caveat**: the vendored feature extractor uses whatever `lief`
version is installed (0.17.6 at training time), while EMBER2018's official
feature_version=2 was computed with lief 0.9.0. The hashed fields
(imports/sections/exports/header enums, which make up most of the 2381
dims) could land in slightly different hash buckets if lief's internal
string representations changed between those versions - training and
inference both use the same (modern) lief, so this is self-consistent, but
it's an honest divergence from the original EMBER training methodology.

## Quantum detector (`file_qsvc`)

`backend/engine/models/quantum/qsvc.py`, feature extraction shared with
`file_ml_or_rf` (same 2381-dim PE features), then mutual-information top-8
feature selection -> quantum feature map (`backend/engine/models/quantum/feature_map.py`,
PennyLane `default.qubit` simulator, ZZ-style circuit, 8 wires) -> classical
RBF-SVM on the resulting embeddings, not a full quantum-kernel Gram matrix
(which would be O(n^2) circuit evaluations - not worth it on this hardware
for what quantum kernels demonstrably deliver here).

```
accuracy:  0.6575
precision: 0.6514
recall:    0.7240
auc:       0.6911
n_train:   2500
n_test:    800
n_wires:   8
```

This is a real result, not a placeholder, and it's modest - consistent with
this repo's own prior quantum-kernel run on UNSW-NB15
(`models/artifacts/model_meta.json`: qsvc acc=0.66 vs rf acc=0.90). Quantum
kernels are the demonstrated weak link on both datasets this project has
tried. `file_qsvc` stays scoped as a small tie-breaker for borderline
classical cases (see `backend/orchestrator/decision.py`'s
`BORDERLINE_LOW`/`BORDERLINE_HIGH` gating), not a primary signal.

## Fixed along the way

Installing `pennylane` (needed for `file_qsvc`) exposed real bugs in the
quantum feature map: `QuantumFeatureMap` had no `_circuit` method for
evaluated output, and no `export_qiskit`/`export_cirq` - added a `_circuit`
alias for `__call__` and both export methods (qiskit via `pennylane`'s own
OpenQASM transform, cirq intentionally `NotImplementedError` - no in-repo
need for it). Separately, the embedding step called the *undecorated*
circuit function directly, which returns unevaluated `ExpectationMP`
measurement objects, not numbers - fixed to use the compiled QNode instead.
It also normalized each batch using that batch's own min/max, so the same
row got a different embedding depending on what else was in its batch -
fixed to normalize per-row instead (matches `QuantumFeatureMap`'s own
per-vector approach), which is what makes results reproducible regardless
of batch size or which subset of the dataset you pass in.

`backend/engine/models/classical/{hst,ngram}.py` (the two unsupervised
online detectors) now checkpoint their learned state to
`backend/engine/models/artifacts/{hst,ngram}_state.joblib` every 500 updates
and on clean process exit, and load it back on startup - previously a
restart reset them to a cold start, throwing away everything they'd learned
from live traffic.

`backend/engine/runtime.py` and `backend/engine/models/loader.py` (a second,
fully dead "engine" path - confirmed zero importers anywhere) removed.

## Security audit

`bandit -r backend`: 3 findings, resolved - one real (bare `except: pass`
around artifact loading in `sgd.py`, now logs), two false positives
annotated with `# nosec` and an explanation (`random.Random(seed)` for
picking HST tree-split features isn't security-sensitive; `--tmpfs /tmp` is
a bwrap argument for the sandboxed child's *own* isolated mount namespace,
not a shared host path).

`pip-audit`: flagged CVEs across the whole system Python environment
(picks up unrelated system tools like `pacman`/`nftables`/`ufw` on this
machine, not just this project's deps). The one actually-relevant hit was
`cryptography` 43.0.3 (multiple CVEs, used for real by
`backend/engine/quarantine.py`) - upgraded to 49.0.0, pinned
`>=44.0.1` as the floor in `backend/pyproject.toml`/`requirements.in`.
`gitleaks` isn't packaged for this distro outside the AUR - not run.

## Known gaps not covered by this pass

- The insider-threat engine (`backend/engine/insider/`) has no baseline/
  risk-state persistence across a backend restart - see
  `hackathon/technical-approach.md` for the full list of what that pass
  deliberately didn't ship.
