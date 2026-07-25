# RAKSHAK Quantum ML Hunter — Project Structure (snapshot)

> **Status: stale snapshot from 2025-10-07.** Large parts of this no longer match the
> real tree (no `rpc/`, `RAKSHAK/`, `infra/`; `backend/engine/models/classical/rf.py` is
> dead code, not active; sandbox/quarantine/rate-limit/config/schemas/artifact_integrity
> modules are missing from this list entirely). Read the actual tree, or `docs/API.md`
> and `docs/ARCHITECTURE.md`, over this file.

This file documents the current repository layout for reference. Paths are relative to the repository root.

## Top-level

- Makefile
- README.md
- MIGRATION.md
- PROJECT_STRUCTURE.md (this file)
- pytest.ini
- pyproject.toml
- setup.py

## configs/
- schema.json
- schema_hash.txt

## backend/api/gRPC/protos/
- decision.proto (authoritative backend and future Qt contract)

## backend/
- __init__.py

### backend/api
- __init__.py
- main.py
- routers/
  - health.py
  - scan.py
  - logs.py
- security/
  - auth.py
- grpc/
  - __init__.py
  - server.py
  - clients/
    - cli_decide.py (legacy client moved here)

### backend/engine
- __init__.py
- runtime.py
- adapters/
  - __init__.py
  - syslog_adapter.py
- features/
  - __init__.py
  - file_features.py
  - log_features.py
- models/
  - __init__.py
  - base.py
  - loader.py
  - artifacts/
  - classical/
    - hst.py
    - ngram.py
    - rf.py
    - sgd.py
    - fuse.py
  - quantum/
    - qsvc.py
- utils/
  - hashing.py

### backend/orchestrator
- __init__.py
- decision.py
- policies.py
- registry.py

## client-qt/
- CMakeLists.txt
- src/ (C++ sources moved from `ui/src`)
- include/ (headers moved from `ui/include`)
- qml/
  - views/MainWindow.qml
  - theme/qtquickcontrols2.conf
- resources.qrc

## rpc/ (legacy)
- clients/
  - cli_decide.py
  - stream_logs.py
- protos/
  - decision.proto (legacy)
- server/
  - server.py (legacy)

## clients/
- python/ (some moved client scripts may be here)

## scripts/
- runner.py
- dev/
  - gen_proto.py

## tests/
- conftest.py
- pytest.ini
- python/
  - unit/
    - features/
      - test_tls_features.py
      - test_statistical_features.py
      - test_flow_features.py
      - test_behavioral_features.py
      - test_features.py
      - test_feature_parity.py
    - models/
      - test_quantum_embedding.py
      - test_model.py
      - test_feature_map_extra.py
    - utils/
      - test_utils.py
      - test_schema_hash.py
  - functional/ (placeholder)
- integration/
  - api/
    - test_inference_api.py
    - test_baseline_smoke.py
- e2e/ (placeholder)

## RAKSHAK/ (legacy QML/QtQuick)
- RAKSHAKContent/ (some QML moved to client-qt)

## ui/ (legacy C++ UI folder; sources moved to client-qt/src but original folder may still exist)

## docs/ (planned)
- ARCHITECTURE.md (TODO)
- API.md (TODO)
- SECURITY.md (TODO)

## infra/ (planned)
- ops/
  - systemd/rakshak-backend.service
  - windows/nssm-install.ps1

---

This snapshot was generated on 2025-10-07.

If you want this in plain `.txt` instead, I can add `PROJECT_STRUCTURE.txt` with the same contents. I can also produce a compact `tree` output if you want every file listed.
