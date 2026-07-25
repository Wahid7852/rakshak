# Trains or serves model workflows for train more models.
#flake8: noqa: E501

"""
just so we don't f up the commands again:

# Windows PowerShell
$env:PYTHONPATH='.'
python -m models.train_more_models --dataset cic2018 --min-acc 0.80 --min-prec 0.80
python -m models.train_more_models --dataset cic2017 --min-acc 0.80 --min-prec 0.80
python -m models.train_more_models --dataset unsw    --min-acc 0.80 --min-prec 0.80

# Arch/Linux
export PYTHONPATH=.
python -m models.train_more_models --dataset cic2018 --min-acc 0.80 --min-prec 0.80
python -m models.train_more_models --dataset cic2017 --min-acc 0.80 --min-prec 0.80
python -m models.train_more_models --dataset unsw    --min-acc 0.80 --min-prec 0.80

"""
from __future__ import annotations
import argparse, os, sys, json, time
from typing import Dict, List, Tuple
import numpy as np, pandas as pd, joblib
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import GradientBoostingClassifier, VotingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import accuracy_score, precision_score, f1_score, roc_auc_score, classification_report
from sklearn.utils.class_weight import compute_class_weight
import xgboost as xgb, lz4.frame, lightgbm as lgb


SCHEMA_JSON = os.path.join("configs","schema.json")
ARTIFACTS   = os.path.join("models","artifacts")
RUNS_DIR    = os.path.join("models","runs")
PIPELINE_VERSION = "1.2.0-more"

DATASET_DEFAULTS = {
  "unsw":   ("data/processed/features/unsw_train.csv",   "data/processed/features/unsw_test.csv"),
  "cic2018":("data/processed/features/cic2018_train.csv","data/processed/features/cic2018_test.csv"),
  "cic2017":("data/processed/features/cic2017_train.csv","data/processed/features/cic2017_test.csv"),
}


def load_schema() -> Tuple[List[str], str]:
    if not os.path.exists(SCHEMA_JSON):
        raise SystemExit(f"Missing {SCHEMA_JSON}. Run a prepare_*.py script first.")
    sch = json.load(open(SCHEMA_JSON,"r",encoding="utf-8"))
    feats = [f["name"] for f in sch["features"]]
    target = sch.get("target","label")
    return feats, target

def load_csv_pair(train_csv, test_csv, feats, target):
    tr = pd.read_csv(train_csv); te = pd.read_csv(test_csv)
    Xtr = tr[feats].values; ytr = tr[target].astype(int).values
    Xte = te[feats].values; yte = te[target].astype(int).values
    return Xtr,ytr,Xte,yte

def evaluate(name, model, X, y) -> Dict[str,float]:
    yhat = model.predict(X)
    proba = None
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X)[:,1]
    elif hasattr(model, "decision_function"):
        s = model.decision_function(X)
        proba = 1/(1+np.exp(-s))
    acc = float(accuracy_score(y,yhat))
    prec= float(precision_score(y,yhat, zero_division=0))
    f1  = float(f1_score(y,yhat, zero_division=0))
    auc = float(roc_auc_score(y, proba)) if proba is not None and len(np.unique(y))==2 else float("nan")
    print(f"\\n== {name} =="); print(classification_report(y,yhat,digits=4))
    print({"acc":acc,"prec":prec,"f1":f1,"auc":auc}); return {"acc":acc,"prec":prec,"f1":f1,"auc":auc}

def build_models(Xtr, ytr, seed=42):
    classes = np.unique(ytr)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=ytr)
    cw = {int(c): float(w) for c,w in zip(classes, weights)}
    models = {}
    models["logreg"] = LogisticRegression(max_iter=2000, class_weight=cw, solver="saga", n_jobs=None)
    k = max(3, int(np.sqrt(len(ytr))//10)*2+1)
    models["knn"] = KNeighborsClassifier(n_neighbors=k, weights="distance", n_jobs=-1)
    models["dt"] = DecisionTreeClassifier(max_depth=20, random_state=seed, class_weight=cw)
    models["gbrt"] = GradientBoostingClassifier(random_state=seed)
    if xgb is not None:
        models["xgb"] = xgb.XGBClassifier(n_estimators=300, max_depth=8, learning_rate=0.1,
                                          subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0,
                                          random_state=seed, n_jobs=-1, tree_method="hist", eval_metric="logloss")

    if lgb is not None:
        models["lgbm"] = lgb.LGBMClassifier(n_estimators=400, num_leaves=64, learning_rate=0.05,
                                            feature_fraction=0.9, bagging_fraction=0.9, bagging_freq=1,
                                            random_state=seed, n_jobs=-1)
    models["mlp"] = MLPClassifier(hidden_layer_sizes=(256,128), batch_size=512, max_iter=200,
                                  early_stopping=True, random_state=seed)
    return models

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="unsw", choices=list(DATASET_DEFAULTS.keys()))
    ap.add_argument("--train-csv", default=None)
    ap.add_argument("--test-csv",  default=None)
    ap.add_argument("--artifacts", default=ARTIFACTS)
    ap.add_argument("--runs-dir",  default=RUNS_DIR)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-acc", type=float, default=0.80)
    ap.add_argument("--min-prec", type=float, default=0.80)
    args = ap.parse_args()

    if args.train_csv is None or args.test_csv is None:
        args.train_csv, args.test_csv = DATASET_DEFAULTS[args.dataset]

    feats, target = load_schema()
    Xtr,ytr,Xte,yte = load_csv_pair(args.train_csv, args.test_csv, feats, target)

    os.makedirs(args.artifacts, exist_ok=True)
    models = build_models(Xtr, ytr, seed=args.seed)

    metrics = {}
    available_for_ensemble = []
    for name, mdl in models.items():
        try:
            mdl.fit(Xtr, ytr)
            m = evaluate(name.upper(), mdl, Xte, yte)
            metrics[name] = m
            joblib.dump({"model": mdl, "cols": feats}, os.path.join(args.artifacts, f"{name}.joblib"), compress= 3)
            if hasattr(mdl, "predict_proba"):
                available_for_ensemble.append((name, mdl))
        except Exception as e:
            print(f"[WARN] Skipping {name} due to error: {e}")

    if len(available_for_ensemble) >= 2:
        ens = VotingClassifier(estimators=[(n, m) for n, m in available_for_ensemble], voting="soft", n_jobs=-1)
        ens.fit(Xtr, ytr)
        metrics["ensemble"] = evaluate("ENSEMBLE (soft)", ens, Xte, yte)
        joblib.dump({"model": ens, "cols": feats}, os.path.join(args.artifacts, "ensemble.joblib"), compress=3)

    ts = time.strftime("%Y%m%d-%H%M%S")
    os.makedirs(args.runs_dir, exist_ok=True)
    with open(os.path.join(args.runs_dir, f"{ts}_{args.dataset}_more.json"), "w", encoding="utf-8") as f:
        json.dump({"pipeline_version": PIPELINE_VERSION, "dataset": args.dataset, "metrics": metrics}, f, indent=2)

    rows = [{"model": k, **v} for k,v in metrics.items()]
    pd.DataFrame(rows).to_csv(os.path.join(args.runs_dir, f"{ts}_{args.dataset}_more.csv"), index=False)

    passes = [k for k,v in metrics.items() if (v.get("acc",0)>=args.min_acc and v.get("prec",0)>=args.min_prec)]
    if not passes:
        print(f"[ERROR] No model met the gate acc>={args.min_acc} & prec>={args.min_prec}", file=sys.stderr)
        sys.exit(1)
    print("[OK] Trained models:", ", ".join(metrics.keys()))
    print("[OK] Passed models:", ", ".join(passes))

if __name__ == "__main__":
    sys.exit(main())
