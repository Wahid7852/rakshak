# Trains or serves model workflows for train baselines.
#flake8: noqa E501
"""
Train fast classical baselines (LogReg, SVM, LightGBM) on flows_v0.csv.

Artifacts:
  - models/artifacts/<MODEL_ID>.joblib
  - models/artifacts/<MODEL_ID>_preproc.joblib
  - models/runs/<TIMESTAMP>_<MODEL_ID>_metrics.json

I will probably add more models later, but these are quick to train and
give a reasonable baseline.
"""

from __future__ import annotations
import argparse, json, os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import joblib, numpy as np, pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC

try:
    from lightgbm import LGBMClassifier, early_stopping
    LGBM_AVAILABLE = True
except Exception:
    LGBM_AVAILABLE = False


# ----------------------------- CLI [Arguments] -------------------------------------- #

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train classical baselines on features CSV")
    p.add_argument("--features", type=str, default="data/processed/features/flows_v0.csv")
    p.add_argument("--schema", type=str, default="configs/schema.json")
    p.add_argument("--out_artifacts", type=str, default="models/artifacts/")
    p.add_argument("--out_runs", type=str, default="models/runs/")
    p.add_argument("--label_col", type=str, default="label")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--test_size", type=float, default=0.2)
    p.add_argument("--metric", type=str, choices=["pr_auc", "f1", "precision_at_recall"], default="pr_auc")
    p.add_argument("--target_recall", type=float, default=0.80)
    p.add_argument("--normalize", type=lambda x: str(x).lower() != "false", default=True)
    p.add_argument("--balance", type=lambda x: str(x).lower() != "false", default=True)
    p.add_argument("--model_set", nargs="*", default=["svm", "lgbm"])
    return p.parse_args()


# ----------------------------- Utils ------------------------------------ #

def utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def safe_predict_proba(clf, X) -> np.ndarray:
    """Return probability-like scores for binary classifiers."""
    if hasattr(clf, "predict_proba"):
        return clf.predict_proba(X)[:, 1]
    if hasattr(clf, "decision_function"):
        s = clf.decision_function(X)
        # min-max normalize to [0,1]
        s = (s - s.min()) / (s.max() - s.min() + 1e-12)
        return s
    # fallback
    preds = clf.predict(X)
    return preds.astype(float)


def max_precision_at_recall(y_true: np.ndarray, y_prob: np.ndarray, target: float) -> float:
    p, r, thr = precision_recall_curve(y_true, y_prob)
    mask = r >= target
    return float(np.max(p[mask])) if np.any(mask) else 0.0


@dataclass
class Result:
    name: str
    model: object
    metrics: Dict[str, float]


# ----------------------------- Preprocessing ---------------------------- #

def build_preprocessor(X_df: pd.DataFrame, schema: Dict, normalize: bool) -> ColumnTransformer:
    features = list(schema["features"])
    X_df = X_df[features].copy()

    # Heuristic: treat "proto" as categorical if present; everything else numeric
    cat_cols = [c for c in X_df.columns if c == "proto"]
    num_cols = [c for c in X_df.columns if c not in cat_cols]

    transformers = []
    if cat_cols:
        transformers.append(
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols)
        )
    num_pipeline_steps = [("impute", SimpleImputer(strategy="constant", fill_value=0))]
    if normalize:
        num_pipeline_steps.append(("scale", StandardScaler()))
    transformers.append(("num", Pipeline(num_pipeline_steps), num_cols))

    pre = ColumnTransformer(transformers=transformers, remainder="drop")
    return pre


# ----------------------------- Metrics ---------------------------------- #

def compute_metrics(y_true: np.ndarray, y_prob: np.ndarray, y_pred: np.ndarray,
                    primary: str, target_recall: float) -> Dict[str, float]:
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    pr_auc = average_precision_score(y_true, y_prob)
    roc = roc_auc_score(y_true, y_prob)
    cm = confusion_matrix(y_true, (y_prob >= 0.5).astype(int)).tolist()

    prec_at_rec = max_precision_at_recall(y_true, y_prob, target_recall)

    primary_map = {
        "pr_auc": pr_auc,
        "f1": f1,
        "precision_at_recall": prec_at_rec,
    }
    metric_primary = float(primary_map[primary])

    return {
        "metric_primary": metric_primary,
        "accuracy": float(acc),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "pr_auc": float(pr_auc),
        "roc_auc": float(roc),
        f"precision_at_recall>={target_recall:.2f}": float(prec_at_rec),
        "confusion_matrix@0.5": cm,
    }


# ----------------------------- Trainers --------------------------------- #


def train_eval_svm(Xtr, ytr, Xte, yte, args) -> Result:
    clf = SVC(
        kernel="rbf",
        probability=True,
        class_weight=("balanced" if args.balance else None),
        random_state=args.seed,
    )
    clf.fit(Xtr, ytr)
    y_prob = clf.predict_proba(Xte)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    m = compute_metrics(yte, y_prob, y_pred, args.metric, args.target_recall)
    return Result("svm_rbf", clf, m)


def train_eval_lgbm(Xtr, ytr, Xte, yte, args) -> Optional[Result]:
    if not LGBM_AVAILABLE:
        return None
    clf = LGBMClassifier(
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=args.seed,
        class_weight=("balanced" if args.balance else None),
    )
    clf.fit(
        Xtr, ytr,
        eval_set=[(Xte, yte)],
        eval_metric="average_precision",
        callbacks=[early_stopping(stopping_rounds=30, verbose=False)],
    )
    y_prob = clf.predict_proba(Xte)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    m = compute_metrics(yte, y_prob, y_pred, args.metric, args.target_recall)
    return Result("lgbm", clf, m)



def main() -> None:
    args = parse_args()

    features_path = Path(args.features)
    schema_path = Path(args.schema)
    out_artifacts = Path(args.out_artifacts)
    out_runs = Path(args.out_runs)

    if not features_path.exists():
        raise FileNotFoundError(f"Features CSV not found: {features_path}")
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")

    ensure_dir(out_artifacts)
    ensure_dir(out_runs)

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    cols = [f["name"] for f in schema["features"]]  # Extract feature names from schema objects

    df = pd.read_csv(features_path)
    if args.label_col not in df.columns:
        # Temporary fallback: synthesize a label if not present
        # (will replace with real label once I make up my damn mind, this is separate from schema)
        num_cols = df.select_dtypes(include=["number"]).columns
        if len(num_cols) == 0:
            raise RuntimeError("No numeric columns to synthesize label from; please add a 'label' column.")
        df[args.label_col] = (df[num_cols[0]] > df[num_cols[0]].median()).astype(int)

    X_df = df[cols].copy()
    y = df[args.label_col].astype(int).values

    # Train/test split
    stratify = y if len(np.unique(y)) > 1 else None
    X_train_df, X_test_df, y_train, y_test = train_test_split(
        X_df, y, test_size=args.test_size, stratify=stratify, random_state=args.seed
    )

    # Preprocessor
    pre = build_preprocessor(X_train_df, schema, normalize=args.normalize)
    X_train = pre.fit_transform(X_train_df)
    X_test = pre.transform(X_test_df)

    results: List[Result] = []
    if "svm" in args.model_set:
        results.append(train_eval_svm(X_train, y_train, X_test, y_test, args))
    if "lgbm" in args.model_set:
        r = train_eval_lgbm(X_train, y_train, X_test, y_test, args)
        if r is not None:
            results.append(r)

    if not results:
        raise RuntimeError("No models were trained. Check --model_set and LightGBM availability.")

    # Pick best by primary metric (descending)
    key = "metric_primary"
    best = sorted(results, key=lambda r: r.metrics.get(key, -1), reverse=True)[0]

    model_id = f"qm-baseline_{schema.get('schema_version','v?')}-{best.name}_py3.13_{utc_ts()}"
    model_path = out_artifacts / f"{model_id}.joblib"
    preproc_path = out_artifacts / f"{model_id}_preproc.joblib"
    metrics_path = out_runs / f"{model_id}_metrics.json"

    joblib.dump(best.model, model_path)
    joblib.dump(pre, preproc_path)

    # enrich metrics
    metrics = dict(best.metrics)
    metrics.update({
        "model_id": model_id,
        "schema_version": schema.get("schema_version"),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
    })
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"[train_baselines] best={best.name} {args.metric}={best.metrics[key]:.4f}  "
          f"PR-AUC={best.metrics['pr_auc']:.4f}  F1={best.metrics['f1']:.4f}")
    print("Artifacts:")
    print("  ", model_path)
    print("  ", preproc_path)
    print("Metrics JSON:")
    print("  ", metrics_path)


if __name__ == "__main__":
    main()
