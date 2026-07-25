# Half-Space Trees streaming anomaly forest.
# Unsupervised/online - calibrates from traffic, no training needed. State
# is checkpointed periodically so a restart doesn't lose it.
from __future__ import annotations

import atexit, logging, math, os, random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import joblib

from backend.orchestrator.types import Decision

from ...features.log_features import log_feature_vector

logger = logging.getLogger(__name__)

_DEFAULT_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "models" / "artifacts"


def _resolve_state_path(filename: str, default_dir: Path = _DEFAULT_ARTIFACTS_DIR) -> Path:
    # checkpoint state gets rewritten at runtime, unlike the pretrained artifacts
    # in the same dir, so it needs somewhere the process actually has write access
    override = os.getenv("RAKSHAK_MODEL_STATE_DIR")
    return (Path(override) if override else default_dir) / filename


ARTIFACT_PATH = _resolve_state_path("hst_state.joblib")
CHECKPOINT_INTERVAL = 500


@dataclass
class HSNode:
    feature: int
    threshold: float
    left: Optional["HSNode"]
    right: Optional["HSNode"]
    depth: int
    n: int = 0


class HalfSpaceForest:
    def __init__(self, n_trees: int = 30, height_limit: int = 9, seed: int = 42):
        self.rng = random.Random(seed)  # nosec B311 - picks tree split features, not security-sensitive
        self.n_trees = n_trees
        self.height_limit = height_limit
        self.trees: List[HSNode] = []
        self.feature_mins: Optional[List[float]] = None
        self.feature_maxs: Optional[List[float]] = None

    def _build_tree(self, depth: int, n_features: int) -> HSNode:
        f = self.rng.randrange(n_features)
        node = HSNode(feature=f, threshold=0.0, left=None, right=None, depth=depth, n=0)
        if depth < self.height_limit:
            node.left = self._build_tree(depth + 1, n_features)
            node.right = self._build_tree(depth + 1, n_features)
        return node

    def _ensure_init(self, x: List[float]) -> None:
        if self.feature_mins is None:
            self.feature_mins = list(x)
            self.feature_maxs = list(x)
            for _ in range(self.n_trees):
                self.trees.append(self._build_tree(0, len(x)))

    def _update_ranges(self, x: List[float]) -> None:
        # always called right after _ensure_init, which populates both
        assert self.feature_mins is not None and self.feature_maxs is not None
        for i, v in enumerate(x):
            if v < self.feature_mins[i]:
                self.feature_mins[i] = v
            if v > self.feature_maxs[i]:
                self.feature_maxs[i] = v

    def _node_threshold(self, i: int) -> float:
        assert self.feature_mins is not None and self.feature_maxs is not None
        lo, hi = self.feature_mins[i], self.feature_maxs[i]
        return (lo + hi) / 2.0

    def update(self, x: List[float]) -> None:
        self._ensure_init(x)
        self._update_ranges(x)
        for t in self.trees:
            node = t
            while node.left is not None and node.right is not None:
                i = node.feature
                node.threshold = self._node_threshold(i)
                node.n += 1
                node = node.left if x[i] <= node.threshold else node.right
            node.n += 1

    def score(self, x: List[float]) -> float:
        self._ensure_init(x)
        scores = []
        for t in self.trees:
            node = t
            s = 0.0
            while node.left is not None and node.right is not None:
                i = node.feature
                thr = self._node_threshold(i)
                visits = max(node.n, 1)
                s += 1.0 / math.sqrt(visits)
                node = node.left if x[i] <= thr else node.right
            visits = max(node.n, 1)
            s += 1.0 / math.sqrt(visits)
            scores.append(s)
        m = sum(scores) / len(scores)
        mx, mn = max(scores), min(scores)
        return 0.0 if mx == mn else (m - mn) / (mx - mn)


class HalfSpaceForestModel:
    def __init__(self, artifact_path: Path = ARTIFACT_PATH):
        self._artifact_path = artifact_path
        self._updates_since_save = 0
        self.line_forest = HalfSpaceForest()
        self.byte_forest = HalfSpaceForest()
        self._load()
        atexit.register(self._save)

    def _load(self) -> None:
        if not self._artifact_path.exists():
            return
        try:
            state = joblib.load(self._artifact_path)
            self.line_forest = state["line_forest"]
            self.byte_forest = state["byte_forest"]
        except Exception:
            logger.warning("failed to load hst state, starting cold", exc_info=True)

    def _save(self) -> None:
        try:
            self._artifact_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump({"line_forest": self.line_forest, "byte_forest": self.byte_forest}, self._artifact_path)
        except Exception:
            logger.warning("failed to save hst state", exc_info=True)

    def _maybe_checkpoint(self) -> None:
        self._updates_since_save += 1
        if self._updates_since_save >= CHECKPOINT_INTERVAL:
            self._save()
            self._updates_since_save = 0

    def predict_proba_line(self, line: str) -> float:
        x = log_feature_vector(line)
        # score-then-update: novelty relative to history seen so far, not
        # biased by this point's own contribution to the split thresholds
        s = self.line_forest.score(x)
        self.line_forest.update(x)
        self._maybe_checkpoint()
        return s

    def predict_proba_bytes(self, b: bytes) -> float:
        head = b[:4096]
        x = [float(len(b)), float(sum(head) / max(1, len(head))), float(len(set(head)))]
        s = self.byte_forest.score(x)
        self.byte_forest.update(x)
        self._maybe_checkpoint()
        return s


class Detector:
    name = "log_hst"
    cost_ms_estimate = 2

    def __init__(self):
        self.model = HalfSpaceForestModel()

    async def score(self, payload, context):
        score = self.model.predict_proba_line(str(payload))
        return Decision(score, 0.5, "malicious" if score >= 0.5 else "benign", self.name)
