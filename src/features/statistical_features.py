# Extracts feature data for statistical features.
"""
statistical_features.py
Enhanced statistical feature extraction from encrypted data.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
import scipy.stats as stats
from scipy.signal import correlate
from collections import Counter


def entropy(data: bytes) -> float:
    """
    Calculate Shannon entropy of byte data.
    
    Args:
        data: Input bytes
        
    Returns:
        Shannon entropy value
    """
    if len(data) == 0:
        return 0.0
        
    # Count byte frequencies
    counts = Counter(data)
    probs = np.array(list(counts.values())) / len(data)
    
    # Calculate entropy
    return -np.sum(probs * np.log2(probs + 1e-10))


def extract_block_stats(data: bytes, block_sizes: Optional[List[int]] = None) -> Dict[str, float]:
    """
    Extract statistical features across different block sizes.
    
    Args:
        data: Input bytes
        block_sizes: List of block sizes to analyze (default [32, 64, 128, 256])
    
    Returns:
        Dict containing block-based statistical features
    """
    if block_sizes is None:
        block_sizes = [32, 64, 128, 256]
    
    features = {}
    
    for size in block_sizes:
        blocks = [data[i:i+size] for i in range(0, len(data), size)]
        if not blocks:
            continue
            
        # Count unique blocks and get frequencies
        block_counts = Counter(blocks)
        unique_ratio = len(block_counts) / len(blocks)
        
        # Calculate block entropy
        probs = np.array(list(block_counts.values())) / len(blocks)
        entropy_val = -np.sum(probs * np.log2(probs + 1e-10))
        # Normalize entropy to [0, 1] range
        max_entropy = np.log2(min(len(blocks), 256))  # max possible entropy for this block size
        entropy_normalized = entropy_val / max_entropy if max_entropy > 0 else 0.0
        
        features[f'block_{size}_unique_ratio'] = min(unique_ratio, 1.0)  # Ensure <= 1
        features[f'block_{size}_entropy'] = min(entropy_normalized, 1.0)  # Ensure <= 1
    
    return features


def extract_ngram_features(data: bytes, ns: Optional[List[int]] = None) -> Dict[str, float]:
    """
    Extract n-gram distribution features.
    
    Args:
        data: Input bytes
        ns: List of n-gram sizes to analyze (default [2, 3, 4])
    
    Returns:
        Dict containing n-gram statistical features
    """
    if ns is None:
        ns = [2, 3, 4]
        
    features = {}
    
    for n in ns:
        ngrams = [data[i:i+n] for i in range(len(data)-n+1)]
        if not ngrams:
            continue
            
        # Get n-gram frequencies
        ngram_counts = Counter(ngrams)
        
        # Calculate distribution statistics
        freqs = np.array(list(ngram_counts.values()))
        
        # Ensure all values are finite and non-negative
        unique_count = len(ngram_counts)
        max_freq = np.max(freqs) / len(ngrams) if len(ngrams) > 0 else 0.0
        
        # Calculate entropy safely
        entropy_val = stats.entropy(freqs) if len(freqs) > 1 else 0.0
        entropy_val = entropy_val if np.isfinite(entropy_val) else 0.0
        
        # Calculate skewness safely to avoid precision loss
        if len(freqs) > 2 and np.std(freqs) > 1e-10:
            skew_val = stats.skew(freqs)
            skew_val = skew_val if np.isfinite(skew_val) else 0.0
        else:
            skew_val = 0.0
        
        features[f'ngram_{n}_unique'] = unique_count
        features[f'ngram_{n}_max_freq'] = max_freq
        features[f'ngram_{n}_entropy'] = entropy_val
        features[f'ngram_{n}_skew'] = skew_val
        
    return features


def moving_entropy(data: bytes, window: int = 512, stride: int = 64) -> Dict[str, float]:
    """
    Calculate entropy statistics using a moving window.
    
    Args:
        data: Input bytes
        window: Window size
        stride: Window stride
    
    Returns:
        Dict containing moving entropy features
    """
    features = {}
    
    entropies = []
    for i in range(0, len(data)-window+1, stride):
        window_data = data[i:i+window]
        counts = Counter(window_data)
        probs = np.array(list(counts.values())) / window
        entropy = -np.sum(probs * np.log2(probs + 1e-10))
        entropies.append(entropy)
        
    if entropies:
        features['entropy_moving_mean'] = np.mean(entropies)
        features['entropy_moving_std'] = np.std(entropies)
        features['entropy_moving_max'] = np.max(entropies)
        features['entropy_moving_min'] = np.min(entropies)
        features['entropy_moving_range'] = np.ptp(entropies)
    
    return features


def autocorrelation_features(data: bytes, max_lag: int = 64) -> Dict[str, float]:
    """
    Extract autocorrelation-based features.
    
    Args:
        data: Input bytes
        max_lag: Maximum lag to consider
        
    Returns:
        Dict containing autocorrelation features
    """
    features = {}
    
    # Convert to numpy array
    signal = np.frombuffer(data, dtype=np.uint8)
    
    # Calculate autocorrelation
    acf = correlate(signal - np.mean(signal), 
                   signal - np.mean(signal), 
                   mode='full')[len(signal)-1:]
    
    # Normalize
    acf = acf / acf[0]
    
    # Get features - ensure all values are finite
    peak_val = np.max(np.abs(acf[1:max_lag])) if max_lag > 1 else 0.0
    mean_val = np.mean(np.abs(acf[1:max_lag])) if max_lag > 1 else 0.0
    std_val = np.std(acf[1:max_lag]) if max_lag > 1 else 0.0
    
    features['autocorr_peak'] = peak_val if np.isfinite(peak_val) else 0.0
    features['autocorr_mean'] = mean_val if np.isfinite(mean_val) else 0.0
    features['autocorr_std'] = std_val if np.isfinite(std_val) else 0.0
    
    # Find first zero crossing
    zero_crossings = np.where(np.diff(np.signbit(acf[:max_lag])))[0]
    features['autocorr_first_zero'] = float(zero_crossings[0]) if len(zero_crossings) > 0 else max_lag
    
    return features


def extract_statistical_features(file_path) -> Dict[str, float]:
    """
    Main function to extract statistical features from a file.
    
    Args:
        file_path: Path to the file to analyze
        
    Returns:
        Dict containing all statistical features
    """
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        
        features = extract_all_statistical_features(data)
        
        # Add basic entropy
        features['entropy'] = entropy(data)
        
        return features
    except Exception as e:
        print(f"Error extracting statistical features from {file_path}: {e}")
        return {}


def extract_all_statistical_features(data: bytes) -> Dict[str, float]:
    """
    Extract all enhanced statistical features.
    
    Args:
        data: Input bytes
        
    Returns:
        Dict containing all statistical features
    """
    features = {}
    
    # Extract block-based features
    features.update(extract_block_stats(data))
    
    # Extract n-gram features
    features.update(extract_ngram_features(data))
    
    # Extract moving entropy features
    features.update(moving_entropy(data))
    
    # Extract autocorrelation features
    features.update(autocorrelation_features(data))
    
    return features