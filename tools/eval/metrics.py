# Provides tooling support for metrics.
#!/usr/bin/env python
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import math

@dataclass
class BinaryMetrics:
    tp: int
    tn: int
    fp: int
    fn: int
    accuracy: float
    precision: float
    recall: float
    f1: float

def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0

def compute_binary(labels: List[int], preds: List[int]) -> BinaryMetrics:
    tp = sum(1 for y, p in zip(labels, preds) if y == 1 and p == 1)
    tn = sum(1 for y, p in zip(labels, preds) if y == 0 and p == 0)
    fp = sum(1 for y, p in zip(labels, preds) if y == 0 and p == 1)
    fn = sum(1 for y, p in zip(labels, preds) if y == 1 and p == 0)
    prec = _safe_div(tp, (tp + fp))
    rec  = _safe_div(tp, (tp + fn))
    acc  = _safe_div(tp + tn, max(1, len(labels)))
    f1   = _safe_div(2*prec*rec, (prec+rec)) if (prec+rec)>0 else 0.0
    return BinaryMetrics(tp, tn, fp, fn, acc, prec, rec, f1)

def percentiles(values: List[float], qs=(0.5, 0.95, 0.99)) -> Dict[str, float]:
    if not values:
        return {f"p{int(q*100)}": 0.0 for q in qs}
    vs = sorted(values)
    n = len(vs)
    out = {}
    for q in qs:
        k = min(n-1, max(0, int(round(q*(n-1)))))
        out[f"p{int(q*100)}"] = float(vs[k])
    return out

def auc_approx(labels: List[int], scores: List[float]) -> Optional[float]:
    # Fast, label-based AUC approximation (no sklearn dependency)
    pairs = sorted(zip(scores, labels), key=lambda x: x[0], reverse=True)
    pos = sum(labels); neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return None
    rank_sum = 0.0
    for i, (_, y) in enumerate(pairs, start=1):
        if y == 1:
            rank_sum += i
    # Mann–Whitney U → AUC
    u = rank_sum - pos*(pos+1)/2
    return u / (pos * neg)
