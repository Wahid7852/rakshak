# Defines backend engine model support for fuse.
class FusionModel:
    def __init__(self):
        from .ngram import NGramModel
        from .sgd import OnlineLogRegModel
        self.a = NGramModel()
        self.b = OnlineLogRegModel()

    def predict_proba_line(self, line: str) -> float:
        return 0.6*self.a.predict_proba_line(line) + 0.4*self.b.predict_proba_line(line)

    def predict_proba_bytes(self, b: bytes) -> float:
        return 0.5*self.a.predict_proba_bytes(b) + 0.5*self.b.predict_proba_bytes(b)
