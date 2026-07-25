# Trains or serves model workflows for hst.

# Minimal Half-Space Trees (streaming-ish) approximate implementation.
# This is a compact, educational version designed for laptop workloads.
# It builds a small ensemble of trees with random feature thresholds
# and updates range statistics online to produce anomaly scores.
from __future__ import annotations
import math, random
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class HSNode:
    feature: int
    threshold: float
    left: Optional['HSNode']
    right: Optional['HSNode']
    depth: int
    n: int = 0  # visits

class HalfSpaceForest:
    def __init__(self, n_trees=30, height_limit=9, seed=42):
        self.rng = random.Random(seed)
        self.n_trees = n_trees
        self.height_limit = height_limit
        self.trees: List[HSNode] = []
        self.feature_mins = None
        self.feature_maxs = None

    def _build_tree(self, depth: int, n_features: int) -> HSNode:
        f = self.rng.randrange(n_features)
        thr = 0.0  # placeholder, will adapt
        node = HSNode(feature=f, threshold=thr, left=None, right=None, depth=depth, n=0)
        if depth < self.height_limit:
            node.left = self._build_tree(depth+1, n_features)
            node.right = self._build_tree(depth+1, n_features)
        return node

    def _ensure_init(self, x):
        import math
        if self.feature_mins is None:
            self.feature_mins = list(x)
            self.feature_maxs = list(x)
            for _ in range(self.n_trees):
                self.trees.append(self._build_tree(0, len(x)))

    def _update_ranges(self, x):
        for i, v in enumerate(x):
            if v < self.feature_mins[i]: self.feature_mins[i] = v
            if v > self.feature_maxs[i]: self.feature_maxs[i] = v

    def _node_threshold(self, node: HSNode, i: int) -> float:
        lo, hi = self.feature_mins[i], self.feature_maxs[i]
        return (lo + hi) / 2.0  # midrange split (cheap, adaptive)

    def update(self, x: List[float]):
        self._ensure_init(x)
        self._update_ranges(x)
        for t in self.trees:
            node = t
            depth = 0
            while node.left is not None and node.right is not None:
                i = node.feature
                thr = self._node_threshold(node, i)
                node.threshold = thr
                node.n += 1
                node = node.left if x[i] <= thr else node.right
                depth += 1
            node.n += 1

    def score(self, x: List[float]) -> float:
        # Path length proxy: fewer splits visited (i.e., low n along path) => more anomalous
        self._ensure_init(x)
        scores = []
        for t in self.trees:
            node = t
            s = 0.0
            while node.left is not None and node.right is not None:
                i = node.feature
                thr = self._node_threshold(node, i)
                visits = max(node.n, 1)
                s += 1.0 / math.sqrt(visits)
                node = node.left if x[i] <= thr else node.right
            visits = max(node.n, 1)
            s += 1.0 / math.sqrt(visits)
            scores.append(s)
        # Normalize to [0,1]
        m = sum(scores) / len(scores)
        mx = max(scores)
        mn = min(scores)
        return 0.0 if mx == mn else (m - mn) / (mx - mn)
