# Real quantum-embedded SVM trained on EMBER2018 (see scripts/dev/train_qsvc.py).
# Modest AUC (~0.69, see artifacts/qsvc_meta.json) - kept as a borderline-case
# tie-breaker only, not a primary signal (see decision.py's gating).
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import joblib

from backend.orchestrator.types import Decision

from ..artifact_integrity import verify as verify_artifact
from ..pe_features import PEFeatureExtractor
from .feature_map import QuantumFeatureMap

logger = logging.getLogger(__name__)

ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "models" / "artifacts" / "qsvc.joblib"


class QSVCModel:
    def __init__(self, artifact_path: Path = ARTIFACT_PATH):
        self.extractor = PEFeatureExtractor(feature_version=2, print_feature_warning=False)
        self.svc = None
        self.scaler = None
        self.feature_idx = None
        self.qfm = None
        if artifact_path.exists():
            try:
                verify_artifact(artifact_path)
                data = joblib.load(artifact_path)
                self.svc = data["svc"]
                self.scaler = data["scaler"]
                self.feature_idx = data["feature_idx"]
                self.qfm = QuantumFeatureMap(n_wires=data["n_wires"], arch_type=data.get("arch_type", "zz"))
            except Exception:
                logger.warning("failed to load qsvc artifact", exc_info=True)

    def predict_proba_bytes(self, b: bytes) -> Optional[float]:
        if self.svc is None or b[:2] != b"MZ":
            return None
        # svc, scaler, feature_idx, and qfm are always set together in __init__
        assert self.scaler is not None and self.qfm is not None
        try:
            vec = self.extractor.feature_vector(b)
            reduced = self.scaler.transform(vec[self.feature_idx].reshape(1, -1))
            embedded = self.qfm(reduced[0]).reshape(1, -1)
            return float(self.svc.predict_proba(embedded)[0, 1])
        except Exception:
            logger.warning("qsvc inference failed", exc_info=True)
            return None


class Detector:
    name = "file_qsvc"
    cost_ms_estimate = 60  # quantum embedding is slower than classical inference

    def __init__(self):
        self.model = QSVCModel()

    async def score(self, payload, context):
        b = bytes(payload) if isinstance(payload, (bytes, bytearray)) else b""
        proba = self.model.predict_proba_bytes(b)
        if proba is None:
            return Decision(0.5, 0.0, "unknown", self.name)
        return Decision(proba, 0.4, "malicious" if proba >= 0.5 else "benign", self.name)
