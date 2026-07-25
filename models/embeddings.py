# models/embeddings.py
from __future__ import annotations
import json, yaml
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FMAP_PATH = ROOT / "configs" / "feature_map.json"
SCHEMA_PATH = ROOT / "configs" / "schema.json"
EMB_PATH = ROOT / "configs" / "embedding.yaml"

# ---------- common utils ----------

def load_feature_order() -> list[str]:
    if FMAP_PATH.exists():
        return json.loads(FMAP_PATH.read_text(encoding="utf-8"))["feature_order"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return [f["name"] for f in schema["features"]]

def load_embedding_cfg() -> dict:
    return yaml.safe_load(EMB_PATH.read_text(encoding="utf-8")) if EMB_PATH.exists() else {"type":"angle"}

def to_numeric_payload(df: pd.DataFrame) -> np.ndarray:
    """Map proto to numeric if present, select numeric cols, return np.float64."""
    if "proto" in df.columns:
        df = df.copy()
        df["proto"] = df["proto"].astype(str).map({"tcp":0.0,"udp":1.0,"icmp":2.0}).fillna(0.0)
    X = df.select_dtypes(include=["number"]).astype(float).values
    return X

# ---------- PennyLane embeddings for VQC ----------

def angle_embedding_matrix(X: np.ndarray, n_qubits: int) -> np.ndarray:
    """Clip/pad to match n_qubits, returns angle matrix (N x n_qubits)."""
    Xc = X.copy()
    if Xc.shape[1] >= n_qubits:
        Xc = Xc[:, :n_qubits]
    else:
        pad = np.zeros((Xc.shape[0], n_qubits - Xc.shape[1]))
        Xc = np.hstack([Xc, pad])
    # map to [-pi, pi] to use as rotation angles
    Xc = np.clip(Xc, -3, 3) / 3.0 * np.pi
    return Xc

def amplitude_embedding_vector(x: np.ndarray, target_dim: int, normalize: bool = True) -> np.ndarray:
    """Build a 2^n amplitude vector from feature row x (strictly for demos)."""
    # pad/truncate to target_dim
    v = x.astype(float)
    if v.size < target_dim:
        v = np.hstack([v, np.zeros(target_dim - v.size)])
    else:
        v = v[:target_dim]
    if normalize:
        n = np.linalg.norm(v) + 1e-12
        v = v / n
    return v

# ---------- Qiskit kernel feature map ----------

def build_qiskit_zz_feature_map(n_qubits: int, reps: int = 2, entanglement: str = "linear"):
    """Return a callable 'feature_map(x: np.ndarray) -> QuantumCircuit' using Qiskit zz_feature_map."""
    # Import lazily to keep module import light
    from qiskit.circuit.library import zz_feature_map
    from qiskit.circuit import ParameterVector, QuantumCircuit
    params = ParameterVector("x", n_qubits)
    qc = zz_feature_map(params, reps=reps, entanglement=entanglement)
    # Closure that assigns parameters
    def _fm(xrow: np.ndarray) -> QuantumCircuit:
        # pad/truncate to n_qubits
        x = xrow.astype(float)
        if x.size < n_qubits:
            x = np.hstack([x, np.zeros(n_qubits - x.size)])
        else:
            x = x[:n_qubits]
        bound = qc.assign_parameters({p: float(x[i]) for i, p in enumerate(params)}, inplace=False)
        return bound
    return _fm
