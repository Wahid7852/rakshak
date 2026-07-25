# Migration from current tree

Move/merge:
- service/main.py  -> backend/api/main.py (split into routers/health.py, scan.py, logs.py)
- models/*.py      -> backend/engine/models/classical/ (hst.py, ngram.py, sgd.py, fuse.py)
- models/embeddings.py, train_qkernel.py, train_qml.py -> backend/engine/models/quantum/
- models/artifacts -> backend/engine/models/artifacts/ (add checksums manifest later)
- scripts/runner.py, parser/syslog_parser.py -> backend/engine/adapters/ and backend/engine/runtime.py
- ui/* (Qt/C++)    -> client-qt/
- RAKSHAK/* (QML)  -> client-qt/qml/ (optional if using QtQuick)

Add:
- backend/api/gRPC/protos/decision.proto (authoritative gRPC contract)
- configs/app.yaml, policies.yaml
- docs/*, .github/workflows/ci.yml, pre-commit

Build:
- Python: `python -m pip install -e ".[dev]"`
- Proto: `python scripts/dev/gen_decider_proto.py`
- Qt bindings: `python scripts/dev/gen_decider_proto.py --cpp`
