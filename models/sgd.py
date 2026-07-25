# Trains or serves model workflows for sgd.

# Tiny online logistic regression with SGD (no external deps)
import math

class OnlineLogReg:
    def __init__(self, n_features, lr=1e-4, l2=1e-4):
        self.w = [0.0] * (n_features + 1)  # bias at end
        self.lr = lr
        self.l2 = l2

    def _dot(self, x):
        s = self.w[-1]
        for i, v in enumerate(x):
            s += self.w[i] * v
        return s

    def predict_proba(self, x):
        z = self._dot(x)
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        else:
            exp_z = math.exp(z)
            return exp_z / (1.0 + exp_z)

    def update(self, x, y):
        p = self.predict_proba(x)
        g = p - y  # gradient for logistic loss
        # L2 + gradient step
        for i, v in enumerate(x):
            self.w[i] = self.w[i] * (1 - self.lr * self.l2) - self.lr * g * v
        self.w[-1] = self.w[-1] * (1 - self.lr * self.l2) - self.lr * g
