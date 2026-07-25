# Tests baseline smoke behavior.
import json, os, subprocess, sys, pytest
from pathlib import Path

_SCHEMA_FEATURE_COUNT = len(json.load(open("configs/schema.json"))["features"])
_QSVC_PATH = Path("models/artifacts/qsvc.joblib")

@pytest.mark.slow
@pytest.mark.skipif(
    os.getenv("RAKSHAK_RUN_TRAINING_SMOKE", "0") != "1",
    reason="set RAKSHAK_RUN_TRAINING_SMOKE=1 to run training smoke test",
)
@pytest.mark.skipif(
    not Path("data/processed/features/flows_v0.csv").exists(),
    reason="baseline smoke dataset is not available",
)
def test_train_and_predict_smoke():
    cmd = [sys.executable, "-m", "models.train_qkernel",
           "--train-csv", "data/processed/features/flows_v0.csv",
           "--test-csv", "data/processed/features/flows_v0.csv",
           "--artifacts", "models/artifacts",
           "--runs-dir", "models/runs",
           "--min-acc", "0.0", "--min-prec", "0.0",
           "--use-quantum", "0"]
    assert subprocess.call(cmd) == 0

    # --use-quantum 0 leaves qsvc.joblib untouched, and predict_qml.py
    # prefers it over rf.joblib if present - move it aside so predict only
    # sees what this test actually trained
    qsvc_backup = None
    if _QSVC_PATH.exists():
        qsvc_backup = _QSVC_PATH.read_bytes()
        _QSVC_PATH.unlink()

    try:
        x = ",".join("0.1" for _ in range(_SCHEMA_FEATURE_COUNT))
        cmd = [sys.executable, "service/predict_qml.py", "--x", x, "--threshold", "0.5"]
        out = subprocess.check_output(cmd, text=True)
        obj = json.loads(out)
        assert "label" in obj and "score" in obj and "model_used" in obj
    finally:
        if qsvc_backup is not None:
            _QSVC_PATH.write_bytes(qsvc_backup)
