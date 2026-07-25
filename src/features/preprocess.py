# Extracts feature data for preprocess.
"""
Feature preprocessing for malware detection model.
"""

import pandas as pd, numpy as np
from pathlib import Path
import logging
from typing import Tuple

def load_and_preprocess_data(features_path: Path, labels_path: Path) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Load features and labels, preprocess by:
    1. Filtering out samples without labels
    2. Removing constant or zero-valued features 
    3. Handling NaN values
    4. Selecting informative features

    Args:
        features_path: Path to features CSV
        labels_path: Path to labels CSV

    Returns:
        Tuple of (preprocessed feature DataFrame, label Series)
    """
    logging.info("Loading data...")
    features = pd.read_csv(features_path)
    labels = pd.read_csv(labels_path)

    # Get base filenames
    features['base_file'] = features['file'].apply(lambda x: x.split('.')[0])
    labels['base_file'] = labels['file'].apply(lambda x: x.split('.')[0])

    # Filter to matching samples
    logging.info(f"Initial samples - Features: {len(features)}, Labels: {len(labels)}")
    features = pd.merge(features, labels[['base_file', 'family']], on='base_file', how='inner')
    logging.info(f"After matching: {len(features)} samples")

    # Drop metadata columns
    features = features.drop(['file', 'base_file'], axis=1)
    label_col = features.pop('family')

    # Remove constant columns
    nunique = features.nunique()
    constant_cols = nunique[nunique == 1].index
    logging.info(f"Dropping {len(constant_cols)} constant columns")
    features = features.drop(constant_cols, axis=1)
    
    # Remove zero columns
    zero_cols = features.columns[(features == 0).all()]
    logging.info(f"Dropping {len(zero_cols)} zero-valued columns")
    features = features.drop(zero_cols, axis=1)

    # Handle NaN values
    nan_cols = features.isna().any()
    logging.info(f"Found {nan_cols.sum()} columns with NaN values")
    features = features.fillna(0)  # Replace NaNs with 0s

    return features, label_col

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True, help="Path to features CSV")
    parser.add_argument("--labels", type=Path, required=True, help="Path to labels CSV")
    parser.add_argument("--outdir", type=Path, required=True, help="Output directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Load and preprocess data
    features, labels = load_and_preprocess_data(args.features, args.labels)

    # Save preprocessed data
    args.outdir.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.outdir / "preprocessed_features.csv", index=False)
    labels.to_csv(args.outdir / "preprocessed_labels.csv", index=False)