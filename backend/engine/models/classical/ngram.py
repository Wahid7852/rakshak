# Online Markov n-gram anomaly scorer, ported from models/ngram.py.
# Unsupervised/online - calibrates from traffic, no training needed. State
# is checkpointed periodically so a restart doesn't lose it.
from __future__ import annotations

import atexit, logging, math, os
from collections import defaultdict, deque
from pathlib import Path
from typing import Iterable, List

import joblib

from backend.orchestrator.types import Decision

from ...features.log_features import tokenize

logger = logging.getLogger(__name__)

_DEFAULT_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "models" / "artifacts"


def _resolve_state_path(filename: str, default_dir: Path = _DEFAULT_ARTIFACTS_DIR) -> Path:
    # checkpoint state gets rewritten at runtime, unlike the pretrained artifacts
    # in the same dir, so it needs somewhere the process actually has write access
    override = os.getenv("RAKSHAK_MODEL_STATE_DIR")
    return (Path(override) if override else default_dir) / filename


ARTIFACT_PATH = _resolve_state_path("ngram_state.joblib")
CHECKPOINT_INTERVAL = 500


class NGramModel:
    def __init__(self, n: int = 3, decay: float = 0.999):
        self.n = n
        self.decay = decay
        self.counts: defaultdict[tuple[tuple[str, ...], str], float] = defaultdict(float)
        self.context_counts: defaultdict[tuple[str, ...], float] = defaultdict(float)
        self.window: deque = deque(maxlen=n - 1)

    def _decay_counts(self) -> None:
        for k in list(self.counts.keys()):
            self.counts[k] *= self.decay
            if self.counts[k] < 1e-6:
                del self.counts[k]
        for ctx_key in list(self.context_counts.keys()):
            self.context_counts[ctx_key] *= self.decay
            if self.context_counts[ctx_key] < 1e-6:
                del self.context_counts[ctx_key]

    def update(self, token: str) -> None:
        if len(self.window) == self.window.maxlen:
            ctx = tuple(self.window)
            self.counts[(ctx, token)] += 1.0
            self.context_counts[ctx] += 1.0
        self.window.append(token)
        self._decay_counts()

    def seq_score(self, seq: Iterable[str]) -> float:
        seq = list(seq)
        if not seq:
            return 0.0
        ll = 0.0
        window: deque = deque(maxlen=self.n - 1)
        for tok in seq:
            if len(window) == window.maxlen:
                ctx = tuple(window)
                numer = self.counts.get((ctx, tok), 0.0) + 0.1
                denom = self.context_counts.get(ctx, 0.0) + 0.1 * 10
                p = numer / denom
                ll += -math.log(max(p, 1e-9))
            window.append(tok)
        avg = ll / max(1, len(seq))
        return 1 - math.exp(-avg)


class _ByteNGram:
    """Fallback n-gram over raw bytes, for the (currently unused by the live
    router) file-scanning entry point - keeps the byte API meaningfully real
    rather than dropping it."""

    def __init__(self, n: int = 3):
        self.n = n
        self.seen: set = set()

    def score(self, b: bytes) -> float:
        grams = [b[i:i + self.n] for i in range(max(0, len(b) - self.n + 1))]
        if not grams:
            return 0.0
        novel = sum(1 for g in grams if g not in self.seen)
        self.seen.update(grams)
        return min(1.0, novel / len(grams))


class Detector:
    name = "log_ngram"
    cost_ms_estimate = 1

    def __init__(self, artifact_path: Path = ARTIFACT_PATH):
        self.model = NGramModel()
        self._byte_model = _ByteNGram()
        self._artifact_path = artifact_path
        self._updates_since_save = 0
        self._load()
        atexit.register(self._save)

    def _load(self) -> None:
        if not self._artifact_path.exists():
            return
        try:
            state = joblib.load(self._artifact_path)
            self.model = state["model"]
            self._byte_model = state["byte_model"]
        except Exception:
            logger.warning("failed to load ngram state, starting cold", exc_info=True)

    def _save(self) -> None:
        try:
            self._artifact_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump({"model": self.model, "byte_model": self._byte_model}, self._artifact_path)
        except Exception:
            logger.warning("failed to save ngram state", exc_info=True)

    async def score(self, payload, context):
        line = str(payload)
        tokens: List[str] = tokenize(line)
        score = self.model.seq_score(tokens)
        for tok in tokens:
            self.model.update(tok)

        self._updates_since_save += 1
        if self._updates_since_save >= CHECKPOINT_INTERVAL:
            self._save()
            self._updates_since_save = 0

        return Decision(score, min(1.0, score), "malicious" if score >= 0.5 else "benign", self.name)
