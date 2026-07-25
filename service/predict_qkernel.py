# service/predict_qkernel.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any
import numpy as np, pandas as pd, joblib

from qiskit_machine_learning.kernels import FidelityStatevectorKernel  # :contentReference[oaicite:9]{index=9}
from qiskit.circuit.library import zz_feature_map                         # :contentReference[oaicite:10]{index=10}

from .feature_map import frame_payload

ROOT = Path(__file__).resolve().parents[1]

class PredictorQKernel:
    def __init__(self, model_id: str):
        A = ROOT / "models" / "artifacts"
        self.model = joblib.load(A / f"{model_id}.joblib")
        self.scaler = joblib.load(A / f"{model_id}_scaler.joblib")
        self.pca = None
        pca_path = A / f"{model_id}_pca.joblib"
        if pca_path.exists():
            self.pca = joblib.load(pca_path)
        self.trainX = np.load(A / f"{model_id}_trainX.npz")["Xtr"]
        meta = json.loads((A / f"{model_id}_meta.json").read_text(encoding="utf-8"))
        self.n_qubits = int(meta["n_qubits"])
        self.model_id = model_id
        self.qkernel = FidelityStatevectorKernel(feature_map=zz_feature_map, enforce_psd=True)

    def _prep_x(self, df: pd.DataFrame) -> np.ndarray:
        # map proto, select numerics
        if "proto" in df.columns:
            df = df.copy()
            df["proto"] = df["proto"].astype(str).map({"tcp":0.0,"udp":1.0,"icmp":2.0}).fillna(0.0)
        X = df.select_dtypes(include=["number"]).astype(float).values
        Xn = self.scaler.transform(X)
        if self.pca is not None:
            Xn = self.pca.transform(Xn)
        return Xn

    def score_one(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        df = frame_payload(payload)
        x = self._prep_x(df)        # shape (1, d')
        # Build kernel vector against training set
        Kx = self.qkernel.evaluate(x, self.trainX)  # shape (1, n_train)
        s = float(self.model.decision_function(Kx)[0])
        prob = float(1.0 / (1.0 + np.exp(-s)))
        label = int(prob >= 0.5)
        return {"model_id": self.model_id, "prob": prob, "label": label}
