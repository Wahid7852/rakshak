# Prepares dataset features for prepare cicids2018.
"""
# Windows PowerShell
$env:PYTHONPATH='.'
python features/prepare_cicids2018.py --input-dir data/raw/cicids2018_csv/

# Arch/Linux
export PYTHONPATH=.
python features/prepare_cicids2018.py --input-dir data/raw/cicids2018_csv/

$env:PYTHONPATH='.'
python -m models.train_qkernel `
  --dataset cic2018 `
  --use-quantum 1 `
  --quantum-topk 10 `
  --min-acc 0.80 --min-prec 0.80 `
  --artifacts models/artifacts `
  --runs-dir models/runs

export PYTHONPATH=.
python -m models.train_qkernel \
  --dataset cic2018 \
  --use-quantum 1 \
  --quantum-topk 10 \
  --min-acc 0.80 --min-prec 0.80 \
  --artifacts models/artifacts \
  --runs-dir models/runs

"""
from __future__ import annotations
"""Prepare CSE-CIC-IDS2018 flow CSVs for training."""
import argparse, os, glob, json, joblib, pandas as pd, numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split

SCHEMA_JSON = os.path.join("config","schema.json")
ARTIFACTS   = os.path.join("models","artifacts")
OUT_TRAIN   = os.path.join("data","processed","features","cic2018_train.csv")
OUT_TEST    = os.path.join("data","processed","features","cic2018_test.csv")
TARGET = "label"
DROP_IF_PRESENT = {"Flow ID","Src IP","Dst IP","Timestamp","SimillarHTTP","Fwd Header Length.1"}

def discover_files(input_dir: str, files: list[str]) -> list[str]:
    if files: return files
    pats = ["*.csv","*.CSV"]
    found = []
    for p in pats:
        found += glob.glob(os.path.join(input_dir, "**", p), recursive=True)
    if not found:
        raise SystemExit(f"No CSVs found under {input_dir}")
    return sorted(found)

def normalize_label(raw: pd.Series) -> pd.Series:
    s = raw.astype(str).str.strip().str.lower()
    benign_vals = {"benign","normal","0"}
    return s.apply(lambda v: 0 if v in benign_vals else 1).astype(int)

def encode_objects(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    encoders = {}
    for col in df.select_dtypes(include=["object"]).columns:
        if col == TARGET: continue
        le = LabelEncoder()
        df[col] = le.fit_transform(df[col].astype(str).fillna(""))
        encoders[col] = le
    return df, encoders

def robust_split(X, y, test_size=0.2, seed=42):
    n_classes = len(np.unique(y)); n=len(y); t=test_size
    if isinstance(t, float):
        min_t = max(n_classes/n + 1e-9, 0.0)
        if t < min_t: t = min(0.5, min_t)
    try:
        return train_test_split(X, y, test_size=t, stratify=y, random_state=seed)
    except Exception:
        return train_test_split(X, y, test_size=t, stratify=None, random_state=seed)

def write_schema(feature_order: list[str]):
    os.makedirs(os.path.dirname(SCHEMA_JSON), exist_ok=True)
    with open(SCHEMA_JSON, "w", encoding="utf-8") as f:
        json.dump({"features":[{"name":c,"dtype":"float"} for c in feature_order],
                   "target": TARGET}, f, indent=2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", default=None)
    ap.add_argument("--files", nargs="*", default=None)
    ap.add_argument("--test-size", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    files = discover_files(args.input_dir, args.files or [])
    frames = []
    for fp in files:
        df = pd.read_csv(fp, low_memory=False)
        for c in list(DROP_IF_PRESENT & set(df.columns)):
            df.drop(columns=[c], inplace=True, errors="ignore")
        label_col=None
        for cand in ["Label","label","class","Class"]:
            if cand in df.columns: label_col=cand; break
        if label_col is None: raise SystemExit(f"No label column found in {fp}")
        df.rename(columns={label_col: TARGET}, inplace=True)
        frames.append(df)

    data = pd.concat(frames, ignore_index=True)
    data[TARGET] = normalize_label(data[TARGET])
    label = data.pop(TARGET); data[TARGET]=label
    data, encoders = encode_objects(data)

    X = data.drop(columns=[TARGET]); y = data[TARGET].astype(int)
    Xtr, Xte, ytr, yte = robust_split(X.values, y.values, test_size=args.test_size, seed=args.seed)

    scaler = StandardScaler(); Xtr_s = scaler.fit_transform(Xtr); Xte_s = scaler.transform(Xte)
    cols=list(X.columns)
    os.makedirs(os.path.dirname(OUT_TRAIN), exist_ok=True)
    pd.DataFrame(Xtr_s, columns=cols).assign(label=ytr).to_csv(OUT_TRAIN, index=False)
    pd.DataFrame(Xte_s, columns=cols).assign(label=yte).to_csv(OUT_TEST, index=False)

    os.makedirs(ARTIFACTS, exist_ok=True)
    joblib.dump({"encoders": encoders, "scaler": scaler, "feature_order": cols}, os.path.join(ARTIFACTS, "encoders.joblib"))
    write_schema(cols)
    print(f"[OK] CIC-IDS2018 -> {OUT_TRAIN} , {OUT_TEST}")
    print("[OK] Saved encoders/scaler ->", os.path.join(ARTIFACTS, "encoders.joblib"))
    print("[OK] Updated schema ->", SCHEMA_JSON)

if __name__ == "__main__":
    main()
