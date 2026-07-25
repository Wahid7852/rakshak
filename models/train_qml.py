# models/train_qml.py
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd

import pennylane as qml
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import average_precision_score, f1_score

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--features", default="data/processed/features/flows_v0.csv")
    p.add_argument("--schema", default="configs/schema.json")
    p.add_argument("--out_runs", default="models/runs")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n_qubits", type=int, default=6)
    p.add_argument("--layers", type=int, default=2)
    p.add_argument("--test_size", type=float, default=0.2)
    return p.parse_args()

def build_vqc(n_qubits, layers):
    dev = qml.device("default.qubit", wires=n_qubits, shots=None)

    @qml.qnode(dev)
    def circuit(x, weights):
        # angle-encode features (truncate/pad to n_qubits)
        for i in range(n_qubits):
            qml.RY(x[i], wires=i)
        # variational layers
        for _ in range(layers):
            for i in range(n_qubits):
                qml.RZ(weights[i], wires=i)
            for i in range(n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])
        return qml.expval(qml.PauliZ(0))
    return circuit

def main():
    args = parse_args()
    np.random.seed(args.seed)

    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    cols = schema["features"]

    df = pd.read_csv(args.features)
    if "label" not in df.columns:
        num = df.select_dtypes(include=["number"]).columns
        df["label"] = (df[num[0]] > df[num[0]].median()).astype(int)

    X = df[cols].copy()
    # keep numeric only for QML; fill cateogry proto if present
    if "proto" in X.columns:
        X["proto"] = X["proto"].astype(str).map({"tcp": 0.0, "udp": 1.0, "icmp": 2.0}).fillna(0.0)
    X = X.select_dtypes(include=["number"]).astype(float).values
    y = df["label"].astype(int).values

    # compress to n_qubits dims
    scaler = StandardScaler().fit(X)
    Xn = scaler.transform(X)
    pca = PCA(n_components=args.n_qubits, random_state=args.seed).fit(Xn)
    Xz = pca.transform(Xn)
    # map to angles [-pi, pi]
    Xz = np.clip(Xz, -3, 3) / 3.0 * np.pi

    stratify = y if len(np.unique(y)) > 1 else None
    Xtr, Xte, ytr, yte = train_test_split(Xz, y, test_size=args.test_size, stratify=stratify, random_state=args.seed)

    circuit = build_vqc(args.n_qubits, args.layers)
    # weights for RZ gates
    weights = np.random.uniform(-np.pi, np.pi, size=args.n_qubits)

    # simple gradient descent
    lr = 0.1
    epochs = 50
    for _ in range(epochs):
        grads = np.zeros_like(weights)
        for i in range(len(weights)):
            w_plus = weights.copy();  w_plus[i] += 1e-3
            w_minus = weights.copy(); w_minus[i] -= 1e-3
            # mean squared error on logits proxy
            loss_p = np.mean((np.array([circuit(x, w_plus) for x in Xtr]) - (2*ytr-1))**2)
            loss_m = np.mean((np.array([circuit(x, w_minus) for x in Xtr]) - (2*ytr-1))**2)
            grads[i] = (loss_p - loss_m) / (2e-3)
        weights -= lr * grads

    # predict scores in [0,1]
    logits = np.array([circuit(x, weights) for x in Xte])
    # map expval in [-1,1] to prob [0,1]
    probs = (logits + 1.0) / 2.0
    preds = (probs >= 0.5).astype(int)

    pr_auc = float(average_precision_score(yte, probs))
    f1 = float(f1_score(yte, preds, zero_division=0))

    out_dir = Path(args.out_runs); out_dir.mkdir(parents=True, exist_ok=True)
    out = {
        "algo": "qml_vqc",
        "n_qubits": args.n_qubits,
        "layers": args.layers,
        "pr_auc": pr_auc,
        "f1": f1,
        "n_test": int(len(yte)),
        "schema_version": schema.get("schema_version"),
    }
    out_path = out_dir / f"qml_vqc_{args.n_qubits}q_{args.layers}l_metrics.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[train_qml] PR-AUC={pr_auc:.3f} F1={f1:.3f}  wrote {out_path}")

if __name__ == "__main__":
    main()
