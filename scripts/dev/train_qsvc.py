#!/usr/bin/env python3
# Trains file_qsvc: top-k feature selection -> quantum feature map ->
# classical SVC on the embeddings (same pattern as models/train_qkernel.py).
# Kept small - quantum kernels are the weak link here (see docs/results.md).
from __future__ import annotations

import argparse, json, pathlib, sys, time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from train_file_rf import load_shards  # noqa: E402
from backend.engine.models.quantum.feature_map import QuantumFeatureMap  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-limit", type=int, default=2500)
    ap.add_argument("--test-limit", type=int, default=800)
    ap.add_argument("--n-wires", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default=str(ROOT / "backend" / "engine" / "models" / "artifacts"))
    args = ap.parse_args()

    print("loading EMBER2018 shards (small sample - quantum embedding is per-row)...")
    X_train, y_train = load_shards("train", range(50, 401, 5), args.train_limit)
    X_test, y_test = load_shards("test", range(10, 101, 3), args.test_limit)
    print(f"train: {X_train.shape[0]} rows ({y_train.sum()} malicious)")
    print(f"test: {X_test.shape[0]} rows ({y_test.sum()} malicious)")

    from sklearn.feature_selection import mutual_info_classif
    from sklearn.preprocessing import MinMaxScaler
    from sklearn.svm import SVC
    from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

    print(f"selecting top-{args.n_wires} features via mutual information...")
    mi = mutual_info_classif(X_train, y_train, random_state=args.seed, discrete_features=False)
    idx = sorted(np.argsort(mi)[::-1][: args.n_wires].tolist())
    print(f"selected feature indices: {idx}")

    scaler = MinMaxScaler(feature_range=(-1, 1))
    Xtr_reduced = scaler.fit_transform(X_train[:, idx])
    Xte_reduced = scaler.transform(X_test[:, idx])

    qfm = QuantumFeatureMap(n_wires=args.n_wires, arch_type="zz", shots=None, seed=args.seed)

    def embed_all(X, label):
        t0 = time.time()
        out = np.asarray([qfm(row) for row in X])
        print(f"  embedded {len(X)} {label} rows in {time.time()-t0:.1f}s")
        return out

    print("quantum-embedding train/test sets...")
    Xtr_embed = embed_all(Xtr_reduced, "train")
    Xte_embed = embed_all(Xte_reduced, "test")

    print("training SVC on quantum embeddings...")
    svc = SVC(kernel="rbf", probability=True, class_weight="balanced", random_state=args.seed)
    svc.fit(Xtr_embed, y_train)

    proba = svc.predict_proba(Xte_embed)[:, 1]
    pred = (proba >= 0.5).astype(int)
    metrics = {
        "accuracy": accuracy_score(y_test, pred),
        "precision": precision_score(y_test, pred, zero_division=0),
        "recall": recall_score(y_test, pred, zero_division=0),
        "auc": roc_auc_score(y_test, proba),
        "n_train": int(X_train.shape[0]),
        "n_test": int(X_test.shape[0]),
        "n_wires": args.n_wires,
    }
    print(json.dumps(metrics, indent=2))

    import joblib

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "svc": svc,
        "scaler": scaler,
        "feature_idx": idx,
        "n_wires": args.n_wires,
        "arch_type": "zz",
    }, out_dir / "qsvc.joblib")

    (out_dir / "qsvc_meta.json").write_text(json.dumps({
        "feature_extractor": "backend.engine.models.pe_features.PEFeatureExtractor(feature_version=2)",
        "quantum_embedding": "backend.engine.models.quantum.feature_map.QuantumFeatureMap(arch='zz')",
        "trained_on": "EMBER2018 (HF mirror cw1521/ember2018-malware), small shard-sampled subset",
        "metrics": metrics,
    }, indent=2))

    from backend.engine.models.artifact_integrity import update_manifest
    update_manifest(out_dir / "qsvc.joblib")

    print(f"wrote {out_dir / 'qsvc.joblib'} and {out_dir / 'qsvc_meta.json'}")


if __name__ == "__main__":
    main()
