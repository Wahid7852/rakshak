# Provides legacy service support for main.
from __future__ import annotations
import os, json, joblib, numpy as np
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from typing import List

ARTIFACTS = os.path.join("models", "artifacts")
API_KEY = os.getenv("RAKSHAK_API_KEY", "")
MAX_FEATS = int(os.getenv("RAKSHAK_MAX_FEATS", "1024"))

class PredictRequest(BaseModel):
    features: List[float] = Field(..., description="Numeric features in training order")

class PredictResponse(BaseModel):
    label: int
    score: float
    model_used: str

def load_bundle():
    qpath = os.path.join(ARTIFACTS, "qsvc.joblib")
    rpath = os.path.join(ARTIFACTS, "rf.joblib")
    if os.path.exists(qpath):
        return joblib.load(qpath), "qsvc"
    if os.path.exists(rpath):
        return joblib.load(rpath), "rf"
    raise RuntimeError("No artifacts found. Train first.")

app = FastAPI(title="RAKSHAK Inference API", version="1.0.0")
_bundle, _name = None, None

@app.on_event("startup")
def _load():
    global _bundle, _name
    _bundle, _name = load_bundle()

@app.get("/health")
def health(): return {"ok": True, "model": _name}

@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest, x_api_key: str | None = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")
    feats = req.features
    if not (1 <= len(feats) <= MAX_FEATS):
        raise HTTPException(status_code=400, detail="bad_input_length")
    if any(not isinstance(v, (int,float)) for v in feats):
        raise HTTPException(status_code=400, detail="bad_input_type")

    cols = _bundle["cols"]; scaler = _bundle.get("scaler")
    if len(feats) != len(cols):
        raise HTTPException(status_code=400, detail="feature_mismatch")
    x = np.array(feats, dtype=float)
    x = scaler.transform([x])[0] if scaler is not None else x
    if _name == "qsvc" and "qmap_cfg" in _bundle:
        from .feature_map import QuantumFeatureMap
        qmap = QuantumFeatureMap(**_bundle["qmap_cfg"])
        X = np.stack([np.array(qmap._circuit(x), dtype=float)], axis=0)
    else:
        X = x.reshape(1,-1)
    try:
        proba = _bundle["model"].predict_proba(X)[0,1]
    except Exception:
        raise HTTPException(status_code=500, detail="inference_error")
    label = int(proba >= 0.5)
    return PredictResponse(label=label, score=float(proba), model_used=_name)
