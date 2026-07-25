# Initializes the models package.
"""RAKSHAK Models Module

Contains model training, quantum kernel methods and evaluation code.
"""

# Import commonly used model classes for convenience
from .hst import HalfSpaceForest
from .ngram import NGramModel
from .sgd import OnlineLogReg
from .fuse import fuse

# don't re-export train_qkernel/train_more_models here - eagerly importing
# them breaks `python -m models.train_qkernel` (silent no-op, see git log)

__all__ = [
    'HalfSpaceForest',
    'NGramModel',
    'OnlineLogReg',
    'fuse',
]
