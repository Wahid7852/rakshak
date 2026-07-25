# Defines source model workflow for base.
"""Base model class for TLS-based malware detection."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np, pandas as pd
from sklearn.preprocessing import StandardScaler

class BaseModel(ABC):
    """Abstract base class for all models."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the model with configuration."""
        self.config = config
        self.model = None
        self.scaler = StandardScaler()
    
    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Train the model."""
        pass
    
    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions."""
        pass
    
    @abstractmethod
    def save(self, path: Path) -> None:
        """Save the model."""
        pass
    
    @abstractmethod
    def load(self, path: Path) -> None:
        """Load the model."""
        pass
    
    def prepare_data(self, X: pd.DataFrame, y: pd.Series) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare data for training/prediction."""
        # Scale features
        X_scaled = pd.DataFrame(
            self.scaler.fit_transform(X),
            columns=X.columns,
            index=X.index
        )
        return X_scaled, y