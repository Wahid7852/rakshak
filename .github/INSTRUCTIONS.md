
# Quantum Malware Hunter — VS Code Agent Instructions

These are the **exact rules and steps** for the VS Code agent (and any human collaborator) to follow in this workspace. The goal is to build a **quantum‑enhanced malware/threat detector** that achieves **≥80% accuracy AND ≥80% precision** on public datasets while staying **secure, memory‑efficient, reproducible, and laptop‑friendly** (Windows 11 + Arch Linux).

---

## 0) TL;DR — Non‑negotiable Rules
1. **Security first.** Never execute unknown binaries or pcap payloads. Treat all inputs as hostile. Work only with **features**, not raw code execution.
2. **Reproducibility.** Use the provided `venv`, `requirements.in → requirements.txt` with **pinned versions + hashes**; use deterministic seeds in every script.
3. **Quality gates.** No PR can merge if `pre-commit`, `ruff`, `mypy`, `pytest -q --maxfail=1`, `bandit`, and `pip-audit` are not green.
4. **Memory efficiency.** Prefer streaming & chunked I/O; avoid copying large arrays; log metrics sparingly; use `float32` where safe.
5. **Documentation always.** Every public function/class: **type hints + Google‑style docstrings** and an example. Every module has a README stub.
6. **Conventional Commits.** `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `perf:`, `refactor:` + concise scope. No generated files in commits.
7. **No secrets in repo.** `.env*` are git‑ignored; run `gitleaks` before pushing.

---

## 1) Project Overview (for the agent to keep in context)
- **Problem.** Detect **unknown** malware/attacks in near‑real‑time from **network flow logs** (Zeek/Suricata) and **static PE features** (EMBER).  
- **Approach.** Strong classical baselines (LightGBM/XGBoost, IsolationForest, OC‑SVM) + **quantum kernels** (Qiskit/PennyLane simulators) on reduced feature sets to test quantum advantage on edge/laptop hardware.  
- **Targets.** Micro‑latency inference path, robust to drift, with transparent metrics and exportable models (ONNX where applicable).  
- **Constraints.** Two developers, Windows + Arch, laptops only, **$0 infra**; optional **GCP credits** for experimentation but default is local CPU.  
- **Success criteria.** On held‑out splits of public datasets, achieve **≥80% accuracy & ≥80% precision**, pass all security & quality gates, and ship a minimal Qt GUI that visualizes streaming alerts.

---

## 2) Repository Layout (agent must create/maintain)

```
qmh/
├─ docs/
│  ├─ ADRs/                      # Architecture Decision Records
│  └─ api/                       # REST/gRPC docs, schemas
├─ data/                         # (gitignored) raw/processed
│  ├─ raw/                       # downloaded datasets
│  └─ processed/                 # feature matrices/parquet
├─ notebooks/                    # quick, read-only experiments
├─ qmh_core/                     # Python backend (models, pipeline)
│  ├─ __init__.py
│  ├─ config.py                  # pydantic settings
│  ├─ features/                  # feature extraction & validation
│  ├─ models/                    # trainers, predictors
│  ├─ quantum/                   # QSVC/VQC wrappers (Qiskit/PennyLane)
│  ├─ drift/                     # drift detection (e.g., ADWIN)
│  ├─ io/                        # streaming adapters (Zeek/Suricata)
│  └─ cli.py                     # entrypoints
├─ cppext/                       # C++ performance extensions (pybind11)
│  ├─ CMakeLists.txt
│  └─ src/
├─ gui_qt/                       # Qt 6 (C++), loads results via gRPC/REST
│  ├─ ui/                        # .ui from Qt Designer (no code edits)
│  ├─ qml/ (optional)
│  └─ src/
├─ proto/                        # service contracts
│  └─ qmh.proto
├─ tests/                        # pytest + hypothesis
├─ .vscode/
│  ├─ settings.json
│  ├─ extensions.json
│  ├─ tasks.json
│  └─ launch.json
├─ requirements.in               # editable high-level deps
├─ requirements.txt              # pinned + hashes (compiled)
├─ constraints.txt               # (optional) org-wide constraints
├─ pyproject.toml                # tool configs (ruff/mypy/black)
├─ .pre-commit-config.yaml
├─ .editorconfig
├─ .gitattributes
├─ .gitignore
├─ .env.example
└─ README.md
```

---

## 3) Workspace & Environment (Windows + Arch)

### 3.1 Python (default: 3.12.8, pip + venv)
**Windows (PowerShell):**
```powershell
python --version
py -3.12 -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip pip-tools wheel
pip-compile --generate-hashes -o requirements.txt requirements.in
pip install -r requirements.txt
pre-commit install
```

**Arch Linux (bash/zsh):**
```bash
python --version
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip pip-tools wheel
pip-compile --generate-hashes -o requirements.txt requirements.in
pip install -r requirements.txt
pre-commit install
```

> Agent rule: **never** install without updating `requirements.in` → `pip-compile` → `requirements.txt`. Always re-run tests after dependency changes.

### 3.2 C/C++ toolchain
- Use **CMake ≥ 3.22**, **Ninja**, **clang** (prefer) or **MSVC** on Windows, **gcc/clang** on Arch.  
- `cppext/` uses **pybind11**; build via `pip install .` or `python -m build` (wheel).  
- Flags: `-O3 -march=native -fvisibility=hidden -fno-exceptions` (where safe), `-Wall -Wextra -Werror`.  
- Sanitizers (dev): `-fsanitize=address,undefined` (Linux/clang).

### 3.3 Recommended VS Code extensions
- Python, C/C++, CMake Tools, **Ruff**, **Mypy**, **Clang-Tidy**, **GitLens**, **Better TOML**, **YAML**, **Proto3** support, **Markdown All in One**.

---

## 4) Dependencies (edit `requirements.in` only)
```txt
# Core
numpy>=1.26
scipy>=1.11
pandas>=2.2
scikit-learn>=1.5
lightgbm>=4.4
xgboost>=2.0
imbalanced-learn>=0.12

# Quantum
qiskit>=1.2
pennylane>=0.42

# IO / streaming
pyarrow>=17.0
fastapi>=0.115
uvicorn[standard]>=0.30
grpcio>=1.65
protobuf>=5.27
pydantic>=2.8

# Dev / QA
pytest>=8.3
hypothesis>=6.112
pytest-cov>=5.0
ruff>=0.6
mypy>=1.11
pre-commit>=3.8
bandit>=1.7
pip-audit>=2.7
gitleaks>=8.18; sys_platform != "win32"

# Build
pybind11>=2.12
build>=1.2
```

Then:
```bash
pip-compile --generate-hashes -o requirements.txt requirements.in
pip install -r requirements.txt
```

---

## 5) Coding Style & Docs

### Python
- **Type hints** everywhere; `from __future__ import annotations`.  
- **Docstrings**: Google style with sections: Args, Returns, Raises, Examples.  
- **Linting/format**: `ruff` (PEP8 + import sort), `black` line‑length `100` (through ruff).  
- **Logging**: use `logging` with structured key/value (no `print`).  
- **Config**: `pydantic` Settings; no hard‑coded paths.  
- **Errors**: narrow `except` clauses; never swallow exceptions.

### C++ (C++20)
- RAII, `std::unique_ptr`/`std::shared_ptr` judiciously; `gsl::span` for views.  
- `-Wall -Wextra -Wpedantic -Werror`; `clang-tidy` with modernize/performance rules.  
- Avoid allocations in hot loops; pre‑allocate; move semantics.  
- Document headers with doxygen comments.

### Documentation
- Each package dir has a `README.md` with **purpose, public APIs, examples, perf notes**.  
- `docs/ADRs/` for key decisions (why we chose X over Y).  
- Generate API docs with `pdoc` or `sphinx` (optional in later milestone).

---

## 6) Data Sources & Handling

### Datasets (download manually into `data/raw/`)
- **CICIDS 2017/2018** (network IDS flows).  
- **UNSW‑NB15** (modern synthetic network traffic).  
- **EMBER** (static PE features; 2017/2018; consider EMBER2024 update).  
- **MalwareBazaar** (hash/sample intel; use API safely; **do not** execute samples).

### Handling rules
- Never commit data. `.gitignore` `data/` by default.  
- Convert CSV → **Parquet** with schema + types; keep a `dataset_card.md` per dataset describing splits & caveats.  
- Validate columns with `pydantic` models before training.  
- Persist trained artifacts to `artifacts/` with metadata JSON (params, seed, dataset hash, metrics).

---

## 7) Features, Methods & Metrics (what the agent builds)

### 7.1 Feature extraction
- **Network (CIC/UNSW)**: flow features (dur, bytes, pkts, flags, proto, IAT stats).  
- **Static PE (EMBER)**: use provided feature vectors; add entropy stats, byte histograms if needed.  
- **Sanitization**: remove obvious identifiers (IP/port leakage), clip/scale robustly; impute safely.

### 7.2 Models
- **Baselines**: `LightGBM`, `XGBoost`, `RandomForest`, `LogReg (class‑weights)`.  
- **Anomaly**: `IsolationForest`, `OneClassSVM`.  
- **Quantum**: 
  - Kernel SVM with **Qiskit** feature maps (e.g., ZZFeatureMap) on PCA‑reduced features.  
  - Variational circuits via **PennyLane** (simulator backend), trained with SPSA/Adam.  
  - Keep qubits small (2–8), shots (512–2048), measure runtime & accuracy vs classical.

### 7.3 Evaluation
- **5× stratified split**; report **Accuracy, Precision, Recall, F1, ROC‑AUC, PR‑AUC**, confusion matrix.  
- **Calibration** (Platt/Isotonic) where needed.  
- **≥80% accuracy & precision** as hard gate for milestone acceptance.  
- **Drift**: add ADWIN/PSI monitors for streaming input (later milestone).

---

## 8) Security & Compliance Checklist (automate in CI)
- **Static analysis**: `ruff`, `mypy`, `clang-tidy`.  
- **Security lint**: `bandit -r qmh_core -s B101,B324` (tune as needed).  
- **Dependency audit**: `pip-audit -r requirements.txt`.  
- **Secrets scan**: `gitleaks detect --source .`.  
- **Sandboxing note**: Only operate on **features/logs**; **never** detonate samples. Use read‑only paths.  
- **Licensing**: record dataset licenses in `docs/dataset_card.md`; ensure compatibility.

---

## 9) CLI, API, and GUI Contracts

### CLI (examples)
```bash
# train classical baseline on CICIDS
python -m qmh_core.cli train --dataset cicids2017 --model lightgbm --seed 42

# train QSVC on reduced features
python -m qmh_core.cli train --dataset unsw-nb15 --model qsvc --qubits 4 --shots 1024

# batch predict
python -m qmh_core.cli predict --model-path artifacts/run_2025-09-29/model.pkl --input data/processed/cicids2017_test.parquet --out predictions.parquet
```

### gRPC (proto excerpt `proto/qmh.proto`)
```proto
syntax = "proto3";
package qmh;

service Detector {
  rpc Health(HealthRequest) returns (HealthReply);
  rpc PredictBatch(PredictRequest) returns (PredictReply);
}

message HealthRequest {}
message HealthReply { string status = 1; }

message PredictRequest { repeated FeatureRow rows = 1; }
message FeatureRow { map<string, double> features = 1; }
message PredictReply { repeated double score = 1; repeated int32 label = 2; }
```

### Qt (C++)
- **Design in Qt Designer** → `.ui` files under `gui_qt/ui/` (no manual edits).  
- C++ Qt app consumes gRPC `Detector` and renders: connection status, last N alerts, metrics box, simple ROC/PR chart image exported from backend.

---

## 10) Tasks for the Agent (do in this order)

1. **Scaffold repo** as per layout above, generate `.gitignore`, `.editorconfig`, `.pre-commit-config.yaml`, `pyproject.toml`, `.vscode/*` skeletons.  
2. **Create venv** and lock deps using `pip-compile`; install tools; enable pre‑commit.  
3. **Implement `qmh_core/config.py`** (pydantic settings, data paths, seeds).  
4. **Implement `qmh_core/features/`**: loaders + validators for CICIDS, UNSW‑NB15, EMBER; CSV→Parquet conversion.  
5. **Implement classical models** in `qmh_core/models/` with a uniform `fit/predict/save/load` API.  
6. **Implement quantum kernels** in `qmh_core/quantum/` behind the same API; use small circuits & simulators.  
7. **Wire CLI** in `qmh_core/cli.py` for train/eval/predict.  
8. **Write tests** (`tests/`) covering loaders, splitters, trainers, serialization; target **≥85% coverage**.  
9. **Add FastAPI/gRPC adapter** (choose one first; gRPC preferred for Qt).  
10. **Add minimal Qt app** that hits `/health` and `/predict` and renders a table + metrics.  
11. **Benchmark** on a 10–20% subset to validate performance, then scale cautiously.  
12. **Document** everything you touch; add ADRs for major choices.

---

## 11) VS Code Project Settings (create in `.vscode/`)

**settings.json**
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["-q"],
  "python.analysis.typeCheckingMode": "basic",
  "editor.formatOnSave": true,
  "editor.rulers": [100],
  "files.trimTrailingWhitespace": true
}
```

**extensions.json**
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-vscode.cpptools",
    "ms-vscode.cmake-tools",
    "charliermarsh.ruff",
    "ms-python.mypy-type-checker",
    "zxh404.vscode-proto3",
    "ms-azuretools.vscode-docker",
    "yzhang.markdown-all-in-one"
  ]
}
```

**tasks.json**
```json
{
  "version": "2.0.0",
  "tasks": [
    { "label": "lint", "type": "shell", "command": "ruff check . && mypy qmh_core" },
    { "label": "tests", "type": "shell", "command": "pytest -q --maxfail=1" },
    { "label": "security", "type": "shell", "command": "bandit -r qmh_core && pip-audit -r requirements.txt" },
    { "label": "gitleaks", "type": "shell", "command": "gitleaks detect --source . || true" }
  ]
}
```

**launch.json** (FastAPI example)
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "API",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["qmh_core.api:app", "--reload"],
      "envFile": "${workspaceFolder}/.env"
    }
  ]
}
```

---

## 12) Example Module Header (agent template)

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable
import numpy as np

@dataclass(slots=True)
class TrainResult:
    model_path: str
    metrics: dict[str, float]

def train_lightgbm(X: np.ndarray, y: np.ndarray, seed: int) -> TrainResult:
    \"\"\"Train a LightGBM classifier.

    Args:
      X: Feature matrix (n_samples, n_features), float32 preferred.
      y: Labels (0/1).
      seed: Deterministic seed.
    Returns:
      TrainResult with saved model path and metrics.
    Raises:
      ValueError: If inputs are malformed.
    Example:
      >>> res = train_lightgbm(X, y, 42)
      >>> res.metrics['precision'] >= 0.8
    \"\"\"
    ...
```

---

## 13) CI (GitHub Actions stub `.github/workflows/ci.yml`)
```yaml
name: ci
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: python -m pip install --upgrade pip pip-tools
      - run: pip-compile --generate-hashes -o requirements.txt requirements.in
      - run: pip install -r requirements.txt
      - uses: pre-commit/action@v3.0.1
      - run: pytest -q --maxfail=1 --disable-warnings -q
      - run: bandit -r qmh_core
      - uses: pypa/gh-action-pip-audit@v1
```

---

## 14) Milestones (agent should track in issues/PRs)
- **M0 (scaffold)**: repo, env, CI, quality gates ✅  
- **M1 (classical baselines)**: ≥80/≥80 on CICIDS or UNSW‑NB15 ✅  
- **M2 (quantum experiments)**: QSVC/VQC on reduced features; compare compute vs quality  
- **M3 (streaming path)**: Zeek/Suricata adapter + FastAPI/gRPC + minimal Qt GUI  
- **M4 (hardening)**: profiling, memory optimization, export (ONNX), docs polish

---

## 15) References (authoritative docs & datasets)
- CICIDS 2017 dataset — UNB CIC: https://www.unb.ca/cic/datasets/ids-2017.html  
- UNSW‑NB15 dataset — UNSW: https://research.unsw.edu.au/projects/unsw-nb15-dataset  
- EMBER dataset — GitHub (Elastic): https://github.com/elastic/ember  
- MalwareBazaar — abuse.ch: https://bazaar.abuse.ch/  
- Zeek NSM — https://zeek.org/  
- Suricata IDS — https://suricata.io/  
- Qiskit docs — https://quantum.cloud.ibm.com/docs  
- PennyLane docs — https://docs.pennylane.ai/  
- pip‑tools — https://pip-tools.readthedocs.io/  
- Bandit — https://bandit.readthedocs.io/  
- pip‑audit — https://github.com/pypa/pip-audit
