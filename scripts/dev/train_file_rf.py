#!/usr/bin/env python3
# Trains file_ml_or_rf on real EMBER2018 features (feature_version=2,
# matches pe_features.py::PEFeatureExtractor). Shards preserve EMBER's
# month-blocked layout (early ones are 100% benign), so sample a spread
# across the range rather than a sequential prefix.
from __future__ import annotations

import argparse, json, pathlib, sys, time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REPO = "cw1521/ember2018-malware"


def load_shards(split: str, shard_ids, limit: int):
    from huggingface_hub import hf_hub_download

    X, y = [], []
    for i in shard_ids:
        if len(X) >= limit:
            break
        path = hf_hub_download(REPO, f"data/ember2018_{split}_{i}.jsonl", repo_type="dataset")
        with open(path) as f:
            for line in f:
                row = json.loads(line)
                if row["y"] not in (0.0, 1.0):  # -1.0 = unlabeled, EMBER's semi-supervised holdout
                    continue
                X.append(row["x"])
                y.append(int(row["y"]))
                if len(X) >= limit:
                    break
    return np.asarray(X, dtype=np.float32), np.asarray(y, dtype=np.int32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-limit", type=int, default=120_000)
    ap.add_argument("--test-limit", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", default=str(ROOT / "backend" / "engine" / "models" / "artifacts"))
    args = ap.parse_args()

    print("downloading EMBER2018 train shards...")
    t0 = time.time()
    X_train, y_train = load_shards("train", range(50, 401, 5), args.train_limit)
    print(f"  {X_train.shape[0]} rows ({y_train.sum()} malicious) in {time.time()-t0:.1f}s")
    if len(set(y_train.tolist())) < 2:
        sys.exit("training set has only one class - adjust shard range")

    print("downloading EMBER2018 test shards...")
    t0 = time.time()
    X_test, y_test = load_shards("test", range(10, 101, 3), args.test_limit)
    print(f"  {X_test.shape[0]} rows ({y_test.sum()} malicious) in {time.time()-t0:.1f}s")

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
    import lightgbm as lgb

    def evaluate(model, name):
        proba = model.predict_proba(X_test)[:, 1]
        pred = (proba >= 0.5).astype(int)
        return {
            "model": name,
            "accuracy": accuracy_score(y_test, pred),
            "precision": precision_score(y_test, pred, zero_division=0),
            "recall": recall_score(y_test, pred, zero_division=0),
            "auc": roc_auc_score(y_test, proba),
        }

    print("training LightGBM...")
    t0 = time.time()
    lgbm = lgb.LGBMClassifier(n_estimators=400, num_leaves=64, random_state=args.seed, verbosity=-1)
    lgbm.fit(X_train, y_train)
    lgbm_metrics = evaluate(lgbm, "lightgbm")
    lgbm_metrics["train_seconds"] = time.time() - t0
    print(json.dumps(lgbm_metrics, indent=2))

    print("training RandomForest (baseline)...")
    t0 = time.time()
    # capped estimators/depth/parallelism - 2381-dim x 100k+ rows otherwise
    # blows past available memory (sklearn RF fully materializes every tree)
    rf = RandomForestClassifier(n_estimators=100, max_depth=16, n_jobs=2, random_state=args.seed)
    rf.fit(X_train, y_train)
    rf_metrics = evaluate(rf, "random_forest")
    rf_metrics["train_seconds"] = time.time() - t0
    print(json.dumps(rf_metrics, indent=2))

    best_model, best_metrics, best_name = (
        (lgbm, lgbm_metrics, "lightgbm") if lgbm_metrics["auc"] >= rf_metrics["auc"] else (rf, rf_metrics, "random_forest")
    )
    print(f"selected: {best_name}")

    import joblib

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "file_rf.joblib"
    joblib.dump(best_model, model_path)

    meta = {
        "active_model": best_name,
        "feature_extractor": "backend.engine.models.pe_features.PEFeatureExtractor(feature_version=2)",
        "feature_dim": X_train.shape[1],
        "trained_on": "EMBER2018 (HF mirror cw1521/ember2018-malware), shard-sampled subset",
        "n_train": int(X_train.shape[0]),
        "n_test": int(X_test.shape[0]),
        "candidates": {"lightgbm": lgbm_metrics, "random_forest": rf_metrics},
    }
    (out_dir / "file_rf_meta.json").write_text(json.dumps(meta, indent=2))

    from backend.engine.models.artifact_integrity import update_manifest
    update_manifest(model_path)

    print(f"wrote {model_path} and {out_dir / 'file_rf_meta.json'}")


if __name__ == "__main__":
    main()
