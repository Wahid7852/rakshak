# Online logistic regression, ported from models/sgd.py. Supervised - loads
# pretrained weights from artifacts/ (scripts/dev/train_log_sgd.py) if
# present, else starts at zero weights (honest neutral prior).
from __future__ import annotations

import json, logging, math
from pathlib import Path
from typing import List, Optional

from backend.orchestrator.types import Decision

from ...features.log_features import VECTOR_WIDTH, log_feature_vector
from ..artifact_integrity import verify as verify_artifact

logger = logging.getLogger(__name__)

ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "models" / "artifacts" / "log_sgd.json"


class OnlineLogReg:
    def __init__(self, n_features: int, lr: float = 1e-4, l2: float = 1e-4):
        self.w = [0.0] * (n_features + 1)  # bias at end
        self.lr = lr
        self.l2 = l2

    def _dot(self, x: List[float]) -> float:
        s = self.w[-1]
        for i, v in enumerate(x):
            s += self.w[i] * v
        return s

    def predict_proba(self, x: List[float]) -> float:
        z = self._dot(x)
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        exp_z = math.exp(z)
        return exp_z / (1.0 + exp_z)

    def update(self, x: List[float], y: float) -> None:
        p = self.predict_proba(x)
        g = p - y
        for i, v in enumerate(x):
            self.w[i] = self.w[i] * (1 - self.lr * self.l2) - self.lr * g * v
        self.w[-1] = self.w[-1] * (1 - self.lr * self.l2) - self.lr * g


def _load_weights(path: Path) -> Optional[List[float]]:
    if not path.exists():
        return None
    try:
        verify_artifact(path)
        data = json.loads(path.read_text())
        w = data.get("weights")
        if isinstance(w, list) and len(w) == VECTOR_WIDTH + 1:
            return [float(v) for v in w]
        logger.warning("log_sgd artifact at %s has unexpected shape, starting cold", path)
    except Exception:
        logger.warning("failed to load log_sgd artifact at %s, starting cold", path, exc_info=True)
    return None


class OnlineLogRegModel:
    def __init__(self, artifact_path: Path = ARTIFACT_PATH):
        self.reg = OnlineLogReg(n_features=VECTOR_WIDTH)
        weights = _load_weights(artifact_path)
        if weights is not None:
            self.reg.w = weights

    def predict_proba_line(self, line: str) -> float:
        return self.reg.predict_proba(log_feature_vector(line))

    def predict_proba_bytes(self, b: bytes) -> float:
        head = b[:4096]
        x = [
            min(1.0, float(len(b)) / (1024 * 1024)),
            min(1.0, float(sum(head) / max(1, len(head))) / 255.0),
            min(1.0, float(len(set(head))) / 256.0),
        ]
        x += [0.0] * (VECTOR_WIDTH - len(x))
        return self.reg.predict_proba(x)


class Detector:
    name = "log_sgd"
    cost_ms_estimate = 1

    def __init__(self):
        self.model = OnlineLogRegModel()

    async def score(self, payload, context):
        score = self.model.predict_proba_line(str(payload))
        return Decision(score, 0.5, "malicious" if score >= 0.5 else "benign", self.name)
