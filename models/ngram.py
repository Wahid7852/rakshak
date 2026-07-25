# Trains or serves model workflows for ngram.

from collections import defaultdict, deque
import math

class NGramModel:
    def __init__(self, n=3, decay=0.999):
        self.n = n
        self.decay = decay
        self.counts = defaultdict(int)
        self.context_counts = defaultdict(int)
        self.window = deque(maxlen=n-1)

    def _decay_counts(self):
        # simple decay by scaling down counts
        for k in list(self.counts.keys()):
            self.counts[k] *= self.decay
            if self.counts[k] < 1e-6:
                del self.counts[k]
        for k in list(self.context_counts.keys()):
            self.context_counts[k] *= self.decay
            if self.context_counts[k] < 1e-6:
                del self.context_counts[k]

    def update(self, token: str):
        if len(self.window) == self.window.maxlen:
            ctx = tuple(self.window)
            self.counts[(ctx, token)] += 1.0
            self.context_counts[ctx] += 1.0
        self.window.append(token)
        self._decay_counts()

    def seq_score(self, seq):
        # average negative log prob over seq
        if not seq:
            return 0.0
        ll = 0.0
        window = deque(maxlen=self.n-1)
        for tok in seq:
            if len(window) == window.maxlen:
                ctx = tuple(window)
                numer = self.counts.get((ctx, tok), 0.0) + 0.1
                denom = self.context_counts.get(ctx, 0.0) + 0.1 * 10
                p = numer / denom
                ll += -math.log(max(p, 1e-9))
            window.append(tok)
        # Normalize to [0,1] using a soft scale
        avg = ll / max(1, len(seq))
        return 1 - math.exp(-avg)  # higher is more anomalous
