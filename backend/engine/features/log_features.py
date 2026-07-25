# Extracts backend engine features for log features.
import re, zlib
from typing import List

from ..utils.entropy import shannon_entropy

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PORT_RE = re.compile(r":\d{1,5}\b")

_STAT_WIDTH = 7
_HASH_BUCKETS = 32
VECTOR_WIDTH = _STAT_WIDTH + _HASH_BUCKETS


def extract_log_features(line: str) -> dict:
    n = len(line) or 1
    digits = sum(1 for c in line if c.isdigit())
    special = sum(1 for c in line if not (c.isalnum() or c.isspace()))
    return {
        "len": len(line),
        "entropy": shannon_entropy(line.encode("utf-8", errors="ignore")),
        "digit_ratio": digits / n,
        "special_ratio": special / n,
        "token_count": len(line.split()),
        "has_ip": bool(_IP_RE.search(line)),
        "has_port": bool(_PORT_RE.search(line)),
    }


def tokenize(line: str) -> List[str]:
    """Tokens for the n-gram model - splits on whitespace and punctuation runs."""
    return re.findall(r"[A-Za-z0-9_./:\-]+", line)


def _hashed_token_freq(tokens: List[str]) -> List[float]:
    """Feature-hashing trick: word-content signal for the linear models.

    Surface stats (length/entropy/digit ratio) carry almost no signal for
    distinguishing e.g. an exception/error line from a routine one - that's
    lexical, not statistical. A deterministic hash (not Python's salted
    hash()) keeps this stable across processes/runs.
    """
    buckets = [0.0] * _HASH_BUCKETS
    if not tokens:
        return buckets
    for tok in tokens:
        b = zlib.crc32(tok.lower().encode("utf-8", errors="ignore")) % _HASH_BUCKETS
        buckets[b] += 1.0
    n = len(tokens)
    return [c / n for c in buckets]


def log_feature_vector(line: str) -> List[float]:
    """Fixed-width numeric vector for the streaming anomaly models (hst, sgd).

    Scaled to roughly [0,1] each - a linear model's decision boundary gets
    dominated/miscalibrated by whichever feature has the largest raw
    magnitude (len ~O(100s) vs hashed frequencies in [0,1]) otherwise.
    """
    f = extract_log_features(line)
    stats = [
        min(1.0, float(f["len"]) / 200.0),
        float(f["entropy"]) / 8.0,
        float(f["digit_ratio"]),
        float(f["special_ratio"]),
        min(1.0, float(f["token_count"]) / 30.0),
        1.0 if f["has_ip"] else 0.0,
        1.0 if f["has_port"] else 0.0,
    ]
    return stats + _hashed_token_freq(tokenize(line))
