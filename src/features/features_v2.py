# Extracts feature data for features v2.
#!/usr/bin/env python3
"""
features_v2.py
Extracts features from encrypted files and their TLS metadata for malware detection.
Modified to handle the different file naming patterns and metadata locations.
"""
from pathlib import Path
from collections import Counter, defaultdict
from math import log2
import numpy as np, csv, json, argparse, time, re
from typing import Dict, List, Any, Optional

def load_metadata(metadata_path: Path) -> Dict[str, Any]:
    """Load and parse the TLS metadata for a file."""
    try:
        return json.loads(metadata_path.read_text())
    except Exception as e:
        print(f"Warning: Could not load metadata from {metadata_path}: {e}")
        return {}

def entropy(b: bytes) -> float:
    """Calculate Shannon entropy at byte level."""
    if not b:
        return 0.0
    cnt = Counter(b)
    L = len(b)
    return -sum((v/L) * log2(v/L) for v in cnt.values() if v > 0)

def byte_hist_topk(b: bytes, k: int = 5) -> List[float]:
    """Get top-k most frequent byte values."""
    arr = np.bincount(np.frombuffer(b, dtype=np.uint8), minlength=256)
    total = arr.sum()
    if total == 0:
        return [0.0]*k
    freqs = arr / total
    top_idx = np.argsort(freqs)[-k:][::-1]
    return [float(freqs[i]) for i in top_idx]

def block_repetition_count(b: bytes, block_size: int = 16) -> int:
    """Count repeated blocks to detect patterns."""
    if len(b) < block_size:
        return 0
    blocks = [b[i:i+block_size] for i in range(0, len(b), block_size)]
    return len(blocks) - len({blk for blk in blocks})

def block_entropy_variance(b: bytes, block_size: int = 1024) -> float:
    """Calculate entropy variance across blocks."""
    ents = []
    for i in range(0, len(b), block_size):
        chunk = b[i:i+block_size]
        if not chunk:
            continue
        ents.append(entropy(chunk))
    return float(np.var(ents)) if ents else 0.0

def get_sample_id(file_path: Path) -> str:
    """Extract sample ID from filename."""
    # Handle sample_XXXXXX.bin.cbc.per_file.enc format
    match = re.match(r'sample_(\d+)\..*', file_path.name)
    if match:
        return match.group(1)
    return file_path.stem

def extract_tls_features(file_data: bytes) -> Dict[str, Any]:
    """Extract TLS-like features from the encrypted data."""
    features = {}
    
    # Total size
    features['total_size'] = len(file_data)
    
    # Basic entropy
    features['entropy'] = entropy(file_data)
    
    # Analyze first block (simulating TLS header)
    header = file_data[:16] if len(file_data) >= 16 else file_data
    features['header_entropy'] = entropy(header)
    
    # Analyze blocks
    features['block_rep16'] = block_repetition_count(file_data, 16)
    features['block_rep32'] = block_repetition_count(file_data, 32)
    features['block_entropy_var'] = block_entropy_variance(file_data, 1024)
    
    # Byte histogram features 
    hist_features = byte_hist_topk(file_data, k=5)
    for i, val in enumerate(hist_features):
        features[f'hist_top_{i}'] = val
    
    # TLS handshake simulation features
    handshake = file_data[:128] if len(file_data) >= 128 else file_data
    features['handshake_entropy'] = entropy(handshake)
    features['handshake_zeroes'] = handshake.count(0) / len(handshake)
    
    # Record size features
    features['avg_record_size'] = len(file_data) / max(1, len(file_data) // 16384)  # TLS max record size
    features['num_full_blocks'] = len(file_data) // 16
    features['partial_block_size'] = len(file_data) % 16
    
    # Byte value distribution features
    byte_vals = np.frombuffer(file_data, dtype=np.uint8)
    features['byte_mean'] = float(np.mean(byte_vals))
    features['byte_std'] = float(np.std(byte_vals))
    features['byte_median'] = float(np.median(byte_vals))
    
    # Block pattern features
    if len(file_data) >= 32:
        blocks = np.array([file_data[i:i+16] for i in range(0, len(file_data)-16, 16)])
        if len(blocks) > 1:
            block_similarities = []
            for i in range(len(blocks)-1):
                similarity = np.sum(blocks[i] == blocks[i+1]) / 16.0
                block_similarities.append(similarity)
            features['block_similarity_mean'] = float(np.mean(block_similarities))
            features['block_similarity_std'] = float(np.std(block_similarities))
        else:
            features['block_similarity_mean'] = 0.0
            features['block_similarity_std'] = 0.0
    else:
        features['block_similarity_mean'] = 0.0
        features['block_similarity_std'] = 0.0
    
    return features

def extract_features_for_file(path: Path) -> Dict[str, Any]:
    """Extract all features for a file."""
    # Read encrypted content
    b = path.read_bytes()
    
    # Get sample ID 
    sample_id = get_sample_id(path)
    
    # Extract features
    features = {
        'sample_id': sample_id,
        'file': path.name
    }
    
    # Add TLS/encrypted data features
    features.update(extract_tls_features(b))
    
    return features

def main():
    parser = argparse.ArgumentParser(description="Extract features from encrypted files")
    parser.add_argument("--indir", default="Dataset/encrypted_samples", 
                      help="Folder containing encrypted files")
    parser.add_argument("--outcsv", default="data/processed/features.csv",
                      help="Output CSV file")
    parser.add_argument("--train-labels", default="Dataset/trainLabels.csv",
                      help="Training labels CSV")
    args = parser.parse_args()

    indir = Path(args.indir)
    outcsv = Path(args.outcsv)
    
    # Ensure output directory exists
    outcsv.parent.mkdir(parents=True, exist_ok=True)
    
    # Load training labels if available
    labels = {}
    if Path(args.train_labels).exists():
        with open(args.train_labels) as f:
            next(f)  # Skip header
            for line in f:
                id, label = line.strip().split(',')
                labels[id] = int(label)
    
    # Extract features
    rows = []
    for p in sorted(indir.glob('*.enc')):
        try:
            feats = extract_features_for_file(p)
            # Add label if available
            if feats['sample_id'] in labels:
                feats['label'] = labels[feats['sample_id']]
            rows.append(feats)
        except Exception as e:
            print(f"Error processing {p}: {e}")
    
    if not rows:
        print("No files processed")
        return
    
    # Determine fieldnames from first row
    fieldnames = list(rows[0].keys())
    
    # Ensure consistent field order
    core_fields = ['sample_id', 'file', 'label']
    feature_fields = sorted(f for f in fieldnames 
                          if f not in core_fields)
    fieldnames = core_fields + feature_fields
    
    # Write features
    print(f"Writing {len(rows)} samples to {outcsv}")
    with open(outcsv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            # Ensure all fields exist
            row_dict = {k: row.get(k, '') for k in fieldnames}
            writer.writerow(row_dict)

    print(f"Extracted {len(rows)} feature sets")
    print(f"Features per sample: {len(feature_fields)}")
    print(f"Output written to {outcsv}")

if __name__ == "__main__":
    main()