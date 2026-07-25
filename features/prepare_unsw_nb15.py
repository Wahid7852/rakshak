# Prepares dataset features for prepare unsw nb15.
#!/usr/bin/env python3
from __future__ import annotations
"""Prepare UNSW-NB15: unified encoders + scaler -> numeric CSVs + schema + encoders.joblib"""
import argparse, os, json, joblib, pandas as pd, numpy as np
from sklearn.preprocessing import LabelEncoder, StandardScaler

SCHEMA_JSON = os.path.join("config","schema.json")
ARTIFACTS   = os.path.join("models","artifacts")
OUT_TRAIN   = os.path.join("data","processed","features","unsw_train.csv")
OUT_TEST    = os.path.join("data","processed","features","unsw_test.csv")
CATEGORICAL = ["proto","service","state"]
TARGET = "label"

def write_schema(feature_order):
    os.makedirs(os.path.dirname(SCHEMA_JSON), exist_ok=True)
    with open(SCHEMA_JSON,"w",encoding="utf-8") as f:
        json.dump({"features":[{"name":c,"dtype":"float"} for c in feature_order],
                   "target": TARGET}, f, indent=2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--test", required=True)
    args = ap.parse_args()

    tr = pd.read_csv(args.train); te = pd.read_csv(args.test)
    for df in (tr, te):
        if "id" in df.columns: df.drop(columns=["id"], inplace=True)

    encoders = {}
    for col in CATEGORICAL:
        if col not in tr.columns or col not in te.columns:
            raise SystemExit(f"Missing categorical column: {col}")
        all_vals = pd.concat([tr[col], te[col]], axis=0).astype(str).fillna("")
        le = LabelEncoder().fit(all_vals)
        tr[col] = le.transform(tr[col].astype(str).fillna(""))
        te[col] = le.transform(te[col].astype(str).fillna(""))
        encoders[col] = le

    drop_cols = [c for c in ["attack_cat"] if c in tr.columns]
    Xtr = tr.drop(columns=[TARGET]+drop_cols, errors="ignore")
    ytr = tr[TARGET].astype(int)
    Xte = te.drop(columns=[TARGET]+drop_cols, errors="ignore")
    yte = te[TARGET].astype(int)

    Xtr = Xtr.apply(pd.to_numeric, errors="coerce").replace([np.inf,-np.inf], np.nan).fillna(0.0)
    Xte = Xte.apply(pd.to_numeric, errors="coerce").replace([np.inf,-np.inf], np.nan).fillna(0.0)

    scaler = StandardScaler()
    Xtr_s = scaler.fit_transform(Xtr.values)
    Xte_s = scaler.transform(Xte.values)

    os.makedirs(os.path.dirname(OUT_TRAIN), exist_ok=True)
    pd.DataFrame(Xtr_s, columns=Xtr.columns).assign(label=ytr.values).to_csv(OUT_TRAIN, index=False)
    pd.DataFrame(Xte_s, columns=Xte.columns).assign(label=yte.values).to_csv(OUT_TEST, index=False)

    os.makedirs(ARTIFACTS, exist_ok=True)
    joblib.dump({"encoders": encoders, "scaler": scaler, "feature_order": list(Xtr.columns)},
                os.path.join(ARTIFACTS,"encoders.joblib"))

    write_schema(list(Xtr.columns))
    print("[OK] wrote", OUT_TRAIN, OUT_TEST)
    print("[OK] encoders ->", os.path.join(ARTIFACTS,"encoders.joblib"))
    print("[OK] schema ->", SCHEMA_JSON)

if __name__ == "__main__":
    main()
