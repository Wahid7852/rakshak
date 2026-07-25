# Initializes the src.features package.
"""
Feature extraction modules for TLS-based malware detection.
"""

from .statistical_features import entropy, extract_statistical_features
from .tls_features import extract_tls_features
from .behavioral_features import extract_behavioral_features
from .flow_features import extract_flow_features

# Main feature extraction function
def extract_features_for_file(file_path):
    """Extract all features for a given file."""
    features = {}
    
    # Add filename
    if hasattr(file_path, 'name'):
        features['file'] = file_path.name
    else:
        import os
        features['file'] = os.path.basename(str(file_path))
    
    # Extract different types of features
    features.update(extract_statistical_features(file_path))
    features.update(extract_tls_features(file_path))
    features.update(extract_behavioral_features(file_path))
    features.update(extract_flow_features(file_path))
    
    return features

__all__ = [
    'entropy',
    'extract_features_for_file',
    'extract_statistical_features',
    'extract_tls_features',
    'extract_behavioral_features', 
    'extract_flow_features'
]