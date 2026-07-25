# GitHub Copilot — Inline Coding Guardrails (Quantum Malware Hunter)

**Audience:** Copilot inline/completion inside VS Code editors.  
**Scope:** Completions for Python, C/C++, proto, and small edits to JSON/YAML config.  
**Single source of truth:** See `INSTRUCTIONS.md` for the project charter, layout, and milestones.

---

## 1) What Copilot should prioritize
1. **Follow repository layout** from `INSTRUCTIONS.md` (`qmh_core/`, `cppext/`, `gui_qt/`, `proto/`, `tests/`, `.vscode/`).
2. **Type‑safe, memory‑efficient code** with clear docstrings and examples. Favor `float32`, iterators, chunked I/O.
3. **Determinism & reproducibility:** honor seeds, no hidden globals, no network access in training code.
4. **Security by default:** do not write code that executes untrusted binaries/pcaps; operate on features/logs only.
5. **Minimal dependencies:** propose stdlib or already‑pinned libs; if a new dep is essential, add it to `requirements.in` (never install ad‑hoc).

---

## 2) Editing boundaries
- ✅ **Allowed:** function bodies, private helpers, unit tests, docstrings, type hints, .proto messages, small config diffs.
- ✅ **Create new files** only under these paths: `qmh_core/*`, `tests/*`, `proto/*`, `cppext/src/*`, `gui_qt/src/*`, `docs/ADRs/*`.
- ❌ **Never edit:** `.venv/`, large data, secrets, or generated artifacts. Do not fetch remote data.
- ❌ **Do not** invent frameworks. If an API choice is needed (FastAPI vs gRPC), prefer **gRPC** per `INSTRUCTIONS.md`.

---

## 3) Style & quality gates (apply in completions)
- Python: Google‑style docstrings, full type hints, `logging` (no `print`), small pure functions, raise specific exceptions.
- C++: RAII, no raw `new/delete`, `-Wall -Wextra -Werror`, move semantics, avoid heap in hot paths.
- Tests: `pytest + hypothesis` where helpful; aim for fast deterministic tests.
- Commit message suggestions: use **Conventional Commits**.
- Every new public API must include an **example** in the docstring and a **unit test**.

---

## 4) “Good” completion templates

### 4.1 Python model trainer skeleton
```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import numpy as np
from sklearn.metrics import precision_score, accuracy_score
import joblib
import lightgbm as lgb

@dataclass(slots=True)
class TrainResult:
    model_path: str
    metrics: dict[str, float]

def train_lightgbm(X: np.ndarray, y: np.ndarray, seed: int = 42) -> TrainResult:
    """Train LightGBM; returns saved path and metrics.

    Args:
      X: (n, d) float32 features.
      y: (n,) int labels in {0,1}.
      seed: deterministic seed.
    """
    assert X.dtype == np.float32
    clf = lgb.LGBMClassifier(random_state=seed, n_estimators=300, subsample=0.8, colsample_bytree=0.8)
    clf.fit(X, y)
    preds = clf.predict(X)
    metrics = {
        "accuracy": float(accuracy_score(y, preds)),
        "precision": float(precision_score(y, preds, zero_division=0)),
    }
    out = "artifacts/lightgbm_model.pkl"
    joblib.dump(clf, out)
    return TrainResult(out, metrics)
```

### 4.2 gRPC proto addition
```proto
message PredictRequest { repeated FeatureRow rows = 1; }
message FeatureRow { map<string, double> features = 1; }
message PredictReply { repeated double score = 1; repeated int32 label = 2; }
```

### 4.3 Test snippet
```python
def test_train_lightgbm_smoke(tmp_path):
    import numpy as np
    X = np.random.RandomState(0).randn(64, 8).astype("float32")
    y = (X[:, 0] > 0).astype(int)
    from qmh_core.models.lightgbm_trainer import train_lightgbm
    res = train_lightgbm(X, y, seed=7)
    assert res.metrics["precision"] >= 0.5
```

---

## 5) Guardrails Copilot must observe
- If a completion would introduce file I/O outside `data/processed/` or `artifacts/`, **avoid** it.
- If code touches dependencies, **emit** a comment: `# NOTE: add <pkg> to requirements.in and recompile lockfile`.
- If unsure about API shape, **prefer** adding TODO with a short rationale rather than guessing framework code.

---

## 6) Quick task checklist Copilot can auto‑suggest
- [ ] Add loader & schema validator in `qmh_core/features/` with `pydantic` models.
- [ ] Add classical baseline trainer with uniform `fit/predict/save/load` API.
- [ ] Add QSVC wrapper using Qiskit on PCA‑reduced features (2–8 qubits).
- [ ] Wire CLI subcommands in `qmh_core/cli.py`: `train`, `eval`, `predict`.
- [ ] Add unit tests for loaders and trainers; ensure fast runtime.
- [ ] Update `docs/ADRs/` when making nontrivial architectural decisions.
