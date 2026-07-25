# flake8: noqa: E501
from __future__ import annotations
import argparse, os, sys, json, time
from typing import List, Tuple, Dict
import numpy as np, pandas as pd, joblib, yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, precision_score, f1_score, roc_auc_score, classification_report
from sklearn.feature_selection import mutual_info_classif

proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

from service.feature_map import QuantumFeatureMap

SCHEMA_JSON = os.path.join("configs","schema.json")
EMBED_YAML  = os.path.join("configs","embedding.yaml")
ARTIFACTS_DIR = os.path.join("models","artifacts")
RUNS_DIR      = os.path.join("models","runs")
PIPELINE_VERSION = "1.2.0"

DATASET_DEFAULTS = {
  "unsw":   ("data/processed/features/unsw_train.csv",   "data/processed/features/unsw_test.csv"),
  "cic2018":("data/processed/features/cic2018_train.csv","data/processed/features/cic2018_test.csv"),
  "cic2017":("data/processed/features/cic2017_train.csv","data/processed/features/cic2017_test.csv"),
}


def load_yaml(path):
    with open(path,"r",encoding="utf-8") as f: 
        return yaml.safe_load(f) or {}

def load_schema() -> Tuple[List[str], str]:
    if not os.path.exists(SCHEMA_JSON):
        raise SystemExit(f"Missing {SCHEMA_JSON}. Run the relevant prepare_*.py script first.")
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
    proba = model.predict_proba(X)[:,1] if hasattr(model,"predict_proba") else None
    acc = float(accuracy_score(y,yhat))
    prec= float(precision_score(y,yhat, zero_division=0))
    f1  = float(f1_score(y,yhat, zero_division=0))
    auc = float(roc_auc_score(y, proba)) if proba is not None else float("nan")
    print(f"\\n== {name} =="); print(classification_report(y,yhat,digits=4))
    print({"acc":acc,"prec":prec,"f1":f1,"auc":auc}); return {"acc":acc,"prec":prec,"f1":f1,"auc":auc}


def quantum_embed(X, n_wires=6, shots=None):
    """Transform classical features to quantum feature space using QuantumFeatureMap.
    
    Args:
        X: Input features array of shape (n_samples, n_features)
        n_wires: Number of qubits to use (default: 6)
        shots: Number of measurement shots (None for analytic)
        
    Returns:
        Quantum embedded features array of shape (n_samples, n_wires)
    """
    q = QuantumFeatureMap(n_wires=n_wires, shots=shots)

    # per-row normalization via q(x) - embedding must not depend on batch composition
    X = np.asarray(X, dtype=float)
    return np.stack([q(row) for row in X], axis=0)

def pick_topk_indices(Xtr,ytr,k):
    mi = mutual_info_classif(Xtr,ytr,random_state=42, discrete_features=False)
    idx = np.argsort(mi)[::-1][:k]
    return sorted(idx.tolist())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="unsw", choices=list(DATASET_DEFAULTS.keys()))
    ap.add_argument("--train-csv", default=None)
    ap.add_argument("--test-csv",  default=None)
    ap.add_argument("--artifacts", default=ARTIFACTS_DIR)
    ap.add_argument("--runs-dir",  default=RUNS_DIR)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--min-acc", type=float, default=0.80)
    ap.add_argument("--min-prec", type=float, default=0.80)
    ap.add_argument("--use-quantum", type=int, default=1)
    ap.add_argument("--quantum-topk", type=int, default=10)
    args = ap.parse_args()

    if args.train_csv is None or args.test_csv is None:
        args.train_csv, args.test_csv = DATASET_DEFAULTS[args.dataset]

    feats, target = load_schema()
    Xtr,ytr,Xte,yte = load_csv_pair(args.train_csv, args.test_csv, feats, target)

    rf = RandomForestClassifier(n_estimators=300, n_jobs=-1, random_state=args.seed)
    rf.fit(Xtr,ytr); m_rf = evaluate("RandomForest (classical)", rf, Xte, yte)

    svm = SVC(kernel="rbf", probability=True, class_weight="balanced", random_state=args.seed)
    svm.fit(Xtr,ytr); m_svm = evaluate("SVM RBF (classical)", svm, Xte, yte)

    m_qsvc=None; qsvc=None; qidx=[]
    if args.use_quantum:
        qidx = pick_topk_indices(Xtr,ytr, min(args.quantum_topk, Xtr.shape[1]))
        Xq_tr = Xtr[:, qidx]; Xq_te = Xte[:, qidx]
        cfg = load_yaml(EMBED_YAML) if os.path.exists(EMBED_YAML) else {}
        n_wires = int(cfg.get("n_wires", len(qidx))); shots=None if cfg.get("shots") in (None,"null") else int(cfg.get("shots"))
        Xe_tr = quantum_embed(Xq_tr, n_wires, shots); Xe_te = quantum_embed(Xq_te, n_wires, shots)
        qsvc = SVC(kernel="rbf", probability=True, class_weight="balanced", random_state=args.seed)
        qsvc.fit(Xe_tr,ytr); m_qsvc = evaluate("SVC on Quantum Embeddings", qsvc, Xe_te, yte)

    candidates=[("rf",rf,m_rf),("svm",svm,m_svm)]
    if m_qsvc is not None: candidates.append(("qsvc",qsvc,m_qsvc))
    best = sorted(candidates, key=lambda x:(x[2]["prec"], x[2]["acc"]), reverse=True)[0]
    best_name, best_model, best_metrics = best
    print(f"[INFO] Active model: {best_name} {best_metrics}")

    os.makedirs(args.artifacts, exist_ok=True)
    joblib.dump({"model": rf, "cols": feats}, os.path.join(args.artifacts,"rf.joblib"), compress=3)
    joblib.dump({"model": svm,"cols": feats}, os.path.join(args.artifacts,"svm.joblib"), compress=3)
    if best_name=="qsvc":
        joblib.dump({"model": qsvc, "cols": [feats[i] for i in qidx],
                     "qmap_cfg": load_yaml(EMBED_YAML) if os.path.exists(EMBED_YAML) else {"n_wires": len(qidx), "shots": None},
                     "quantum_subset_idx": qidx},
                    os.path.join(args.artifacts,"qsvc.joblib"), compress=3)
    with open(os.path.join(args.artifacts,"model_meta.json"),"w",encoding="utf-8") as f:
        json.dump({"pipeline_version":PIPELINE_VERSION,"features":feats,"target":target,
                   "dataset": args.dataset,
                   "active":best_name,"metrics":{"rf":m_rf,"svm":m_svm,"qsvc":m_qsvc},
                   "quantum_subset_idx": qidx}, f, indent=2)
    with open(os.path.join(args.artifacts,"active.txt"),"w",encoding="utf-8") as f: f.write(best_name+"\\n")

    if not (best_metrics["acc"]>=args.min_acc and best_metrics["prec"]>=args.min_prec):
        print(f"[ERROR] Quality gate failed for active '{best_name}': acc={best_metrics['acc']:.3f} prec={best_metrics['prec']:.3f}", file=sys.stderr)
        sys.exit(1)

    ts = time.strftime("%Y%m%d-%H%M%S"); os.makedirs(args.runs_dir, exist_ok=True)
    with open(os.path.join(args.runs_dir, ts+f"_{args.dataset}_metrics.json"),"w",encoding="utf-8") as f:
        json.dump({"rf":m_rf,"svm":m_svm,"qsvc":m_qsvc}, f, indent=2)

    print("[OK] Quality gate passed. Artifacts ->", args.artifacts)


if __name__ == "__main__":
    main()
