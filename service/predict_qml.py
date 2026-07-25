# Provides legacy service support for predict qml.
from __future__ import annotations
import argparse, json, logging, os, pathlib, sys, joblib, numpy as np

# run directly (not as -m), so make the repo root importable for absolute imports
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

logger = logging.getLogger(__name__)

ARTIFACTS = os.path.join("models", "artifacts")

def load_bundle():
    # fall back to rf on any load failure, not just absence - a committed
    # .joblib can be unpicklable under a different numpy/sklearn version
    candidates = [
        (os.path.join(ARTIFACTS, "qsvc.joblib"), "qsvc"),
        (os.path.join(ARTIFACTS, "rf.joblib"), "rf"),
    ]
    last_error = None
    for path, name in candidates:
        if not os.path.exists(path):
            continue
        try:
            return joblib.load(path), name
        except Exception as e:
            logger.warning("failed to load %s artifact at %s, trying next candidate", name, path, exc_info=True)
            last_error = e
    if last_error is not None:
        raise RuntimeError(f"No artifact could be loaded. Last error: {last_error}") from last_error
    raise RuntimeError("No artifacts found. Train first.")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--x", required=True, help="Comma-separated numeric features in training order")
    p.add_argument("--threshold", type=float, default=0.5)
    args = p.parse_args()

    bundle, name = load_bundle()
    cols = bundle["cols"]
    scaler = bundle.get("scaler")
    x = np.array([float(v) for v in args.x.split(",")], dtype=float)
    if len(x) != len(cols):
        raise SystemExit(f"Feature length mismatch: got {len(x)} expected {len(cols)}")
    x = scaler.transform([x])[0] if scaler is not None else x
    if name == "qsvc" and "qmap_cfg" in bundle:
        from service.feature_map import QuantumFeatureMap
        qmap = QuantumFeatureMap(**bundle["qmap_cfg"])
        X = np.stack([np.array(qmap._circuit(x), dtype=float)], axis=0)
    else:
        X = x.reshape(1, -1)
    proba = bundle["model"].predict_proba(X)[0,1]
    label = int(proba >= args.threshold)
    print(json.dumps({"label": label, "score": float(proba), "model_used": name}, indent=2))

if __name__ == "__main__":
    main()
