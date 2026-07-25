# flake8: noqa E501
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List

import joblib, numpy as np, pandas as pd

from .model_registry import get_current_model_info

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "configs" / "schema.json"

def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

class Predictor:
    def __init__(self) -> None:
        self.schema = _load_schema()
        info = get_current_model_info()
        self.model_id = info.model_id
        self.preproc = joblib.load(info.preproc_path)
        self.model = joblib.load(info.model_path)
        self.feature_order: List[str] = [f["name"] for f in self.schema["features"]]

    def _validate_and_frame(self, payload: Dict[str, Any]) -> pd.DataFrame:
        missing = [k for k in self.feature_order if k not in payload]
        if missing:
            raise ValueError(f"Missing required keys: {missing}")
        # order payload by schema features and make single-row DF
        ordered = {k: [payload.get(k)] for k in self.feature_order}
        df = pd.DataFrame(ordered)
        # minimal coercion; rely on preprocessor for stricter handling
        return df

    def score_one(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        df = self._validate_and_frame(payload)
        X = self.preproc.transform(df)
        # binary classifiers expected → prob for class 1
        if hasattr(self.model, "predict_proba"):
            prob = float(self.model.predict_proba(X)[:, 1][0])
        elif hasattr(self.model, "decision_function"):
            s = float(self.model.decision_function(X)[0])
            # min-max like normalization for a single score → sigmoid fallback
            prob = float(1.0 / (1.0 + np.exp(-s)))
        else:
            # fallback to predicted label as 0/1
            prob = float(self.model.predict(X)[0])
        label = int(prob >= 0.5)
        return {"model_id": self.model_id, "prob": prob, "label": label}
