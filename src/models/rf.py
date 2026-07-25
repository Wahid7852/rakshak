# Defines source model workflow for rf.
"""Random Forest model implementation for TLS-based malware detection."""

import numpy as np, pandas as pd
from pathlib import Path
from typing import Dict, Any
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV

from .base import BaseModel

class RandomForestModel(BaseModel):
    """Random Forest classifier with optimization and evaluation capabilities."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model = RandomForestClassifier(
            **config.get('hyperparameters', {})
        )
    
    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Train the model, with optional hyperparameter optimization."""
        X_scaled, y = self.prepare_data(X, y)
        
        if self.config.get('optimization', {}).get('enabled', False):
            param_grid = self.config['optimization']['param_grid']
            cv_folds = self.config['optimization'].get('cv_folds', 5)
            
            grid_search = GridSearchCV(
                self.model, param_grid, cv=cv_folds,
                scoring='f1_weighted', n_jobs=-1
            )
            grid_search.fit(X_scaled, y)
            
            self.model = grid_search.best_estimator_
        else:
            self.model.fit(X_scaled, y)
    
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Make predictions on new data."""
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Get probability estimates for predictions."""
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)
    
    def save(self, path: Path) -> None:
        """Save the model and its metadata."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'config': self.config,
            'feature_names': None,  # Set when saving specific model
            'classes': self.model.classes_.tolist() if self.model else None
        }
        joblib.dump(model_data, path)
    
    def load(self, path: Path) -> None:
        """Load the model and its metadata."""
        model_data = joblib.load(path)
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.config = model_data['config']