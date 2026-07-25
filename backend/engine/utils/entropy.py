# Supports backend engine runtime behavior for entropy.
from collections import Counter
import math


def shannon_entropy(b: bytes | bytearray) -> float:
    if not b:
        return 0.0
    n = len(b)
    counts = Counter(b)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())
