# Extracts feature data for features enhanced.
"""
features_enhanced.py
Enhanced feature extraction for encrypted file classification.

This module provides comprehensive feature extraction by combining:
1. Basic statistical features (entropy, size, etc.)
2. Enhanced statistical features (blocks, n-grams, etc.)
3. TLS protocol features (record types, versions, etc.)
4. Flow/timing features (sizes, durations, etc.)
5. Behavioral features (patterns, renegotiation, etc.)
"""

import argparse
from pathlib import Path
import numpy as np, yaml, json, csv
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.features.statistical_features import extract_all_statistical_features
from src.features.tls_features import extract_all_tls_features
from src.features.flow_features import extract_all_flow_features
from src.features.behavioral_features import extract_all_behavioral_features


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load feature extraction configuration from YAML."""
    try:
        with open(config_path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: Could not load config from {config_path}: {e}")
        return {}


def load_metadata(metadata_path: Path) -> Optional[Dict[str, Any]]:
    """Load file metadata if available."""
    try:
        with open(metadata_path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load metadata from {metadata_path}: {e}")
        return None


def extract_features_for_file(filepath: Path, 
                            config: Dict[str, Any],
                            metadata_dir: Optional[Path] = None) -> Dict[str, float]:
    """
    Extract all enabled features for a file.
    
    Args:
        filepath: Path to encrypted file
        config: Feature extraction configuration
        metadata_dir: Optional path to metadata directory
        
    Returns:
        Dict containing all extracted features
    """
    features = {'file': filepath.name}
    
    # Load file content
    try:
        data = filepath.read_bytes()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return features
        
    # Load metadata if available
    metadata = None
    if metadata_dir:
        meta_path = metadata_dir / f"{filepath.name}.meta.json"
        if meta_path.exists():
            metadata = load_metadata(meta_path)
            
    # Extract all feature types if enabled
    if config.get('feature_types', {}).get('basic', True):
        # Basic features always extracted
        features['size'] = len(data)
        
    if config.get('feature_types', {}).get('enhanced', True):
        # Enhanced statistical features
        stats_features = extract_all_statistical_features(data)
        features.update({
            f'enhanced_{k}': v for k, v in stats_features.items()
        })
        
    if config.get('feature_types', {}).get('tls', True):
        # TLS protocol features
        tls_features = extract_all_tls_features(data)
        features.update({
            f'tls_{k}': v for k, v in tls_features.items()
        })
        
    if config.get('feature_types', {}).get('flow', True):
        # Flow and timing features
        flow_features = extract_all_flow_features(data, metadata)
        features.update({
            f'flow_{k}': v for k, v in flow_features.items()
        })
        
    if config.get('feature_types', {}).get('behavioral', True):
        # Behavioral pattern features
        behavior_features = extract_all_behavioral_features(data, metadata)
        features.update({
            f'behavior_{k}': v for k, v in behavior_features.items()
        })
        
    return features


def save_features(features: List[Dict[str, float]], 
                 output_path: Path,
                 config: Dict[str, Any]):
    """
    Save extracted features to file.
    
    Args:
        features: List of feature dictionaries
        output_path: Path to save features
        config: Feature extraction configuration
    """
    if not features:
        print("No features to save")
        return
        
    # Get all feature fields
    fields = set()
    for feat_dict in features:
        fields.update(feat_dict.keys())
    fields = sorted(fields)
    
    # Save features
    format = config.get('output', {}).get('format', 'csv')
    if format == 'csv':
        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for feat_dict in features:
                # Ensure all fields exist
                row = {k: feat_dict.get(k, 0.0) for k in fields}
                writer.writerow(row)
                
    elif format == 'json':
        output = {
            'features': features,
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'config': config
            }
        }
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
            
    print(f"Saved {len(features)} feature vectors to {output_path}")
    

def main():
    parser = argparse.ArgumentParser(
        description="Extract comprehensive features from encrypted files"
    )
    parser.add_argument('--config', 
                       default='configs/feature_configs.yaml',
                       help='Feature extraction configuration file')
    parser.add_argument('--indir',
                       default='data/encrypted',
                       help='Input directory containing encrypted files')
    parser.add_argument('--outpath',
                       default='data/processed/features.csv',
                       help='Output path for extracted features')
    parser.add_argument('--metadata-dir',
                       help='Optional directory containing file metadata')
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(Path(args.config))
    if not config:
        print("Could not load configuration, using defaults")
        config = {'feature_types': {}, 'output': {'format': 'csv'}}
        
    # Process files
    indir = Path(args.indir)
    if not indir.exists():
        print(f"Input directory {indir} does not exist")
        return
        
    metadata_dir = Path(args.metadata_dir) if args.metadata_dir else None
    if metadata_dir and not metadata_dir.exists():
        print(f"Metadata directory {metadata_dir} does not exist")
        metadata_dir = None
        
    # Extract features
    all_features = []
    for filepath in sorted(indir.rglob('*')):
        if not filepath.is_file() or filepath.name.endswith('.meta.json'):
            continue
            
        try:
            features = extract_features_for_file(filepath, config, metadata_dir)
            all_features.append(features)
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            continue
            
    if not all_features:
        print("No files processed")
        return
        
    # Save features
    outpath = Path(args.outpath)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    save_features(all_features, outpath, config)


if __name__ == '__main__':
    main()