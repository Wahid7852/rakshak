# PE-malware classifier trained on EMBER2018 (scripts/dev/train_file_rf.py).
# Only scores actual PE files (`MZ` header) - never trained on anything else.
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import joblib

from backend.orchestrator.types import Decision

from ..artifact_integrity import verify as verify_artifact
from ..pe_features import PEFeatureExtractor

logger = logging.getLogger(__name__)

ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "models" / "artifacts" / "file_rf.joblib"


class FileRFModel:
    def __init__(self, artifact_path: Path = ARTIFACT_PATH):
        self.model = None
        self.extractor = PEFeatureExtractor(feature_version=2, print_feature_warning=False)
        if artifact_path.exists():
            try:
                verify_artifact(artifact_path)
                self.model = joblib.load(artifact_path)
            except Exception:
                logger.warning("failed to load file_rf artifact", exc_info=True)

    def predict_proba_bytes(self, b: bytes) -> Optional[float]:
        if self.model is None or b[:2] != b"MZ":
            return None
        try:
            vec = self.extractor.feature_vector(b).reshape(1, -1)
            return float(self.model.predict_proba(vec)[0, 1])
        except Exception:
            logger.warning("PE feature extraction/inference failed", exc_info=True)
            return None


class Detector:
    name = "file_ml_or_rf"
    cost_ms_estimate = 20

    def __init__(self):
        self.model = FileRFModel()

    async def score(self, payload, context):
        b = bytes(payload) if isinstance(payload, (bytes, bytearray)) else b""
        proba = self.model.predict_proba_bytes(b)
        if proba is None:
            return Decision(0.5, 0.0, "unknown", self.name)
        return Decision(proba, 0.6, "malicious" if proba >= 0.5 else "benign", self.name)
