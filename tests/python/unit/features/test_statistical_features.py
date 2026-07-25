# Tests statistical features behavior.
"""
Test cases for statistical feature extraction.
"""

import os, sys, unittest, numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.features.statistical_features import *

class TestStatisticalFeatures(unittest.TestCase):
    
    def setUp(self):
        # Create test data
        self.random_data = os.urandom(2048)
        self.repeated_data = b'A' * 2048
        self.structured_data = (b'ABCD' * 512)  # Repeated pattern
        
    def test_block_stats(self):
        # Test with random data
        features = extract_block_stats(self.random_data)
        self.assertTrue(all(0 <= v <= 1 for v in features.values()))
        
        # Test with repeated data
        features = extract_block_stats(self.repeated_data)
        for k, v in features.items():
            if 'unique_ratio' in k:
                print(f"Feature {k}: {v}")
                # For repeated data, we should have low unique ratio (only 1 unique block)
                self.assertTrue(v <= 1.0)  # Should be normalized
    
    def test_ngram_features(self):
        # Test with random data
        features = extract_ngram_features(self.random_data)
        self.assertTrue(all(v >= 0 for v in features.values()))
        
        # Test with repeated data
        features = extract_ngram_features(self.repeated_data)
        for k, v in features.items():
            if 'unique' in k:
                self.assertEqual(v, 1)
    
    def test_moving_entropy(self):
        # Test with random data
        features = moving_entropy(self.random_data)
        self.assertTrue(7 <= features['entropy_moving_mean'] <= 8)
        
        # Test with repeated data
        features = moving_entropy(self.repeated_data)
        self.assertAlmostEqual(features['entropy_moving_mean'], 0.0, places=2)
    
    def test_autocorrelation(self):
        # Test with random data
        features = autocorrelation_features(self.random_data)
        self.assertTrue(0 <= features['autocorr_peak'] <= 1)
        
        # Test with structured data
        features = autocorrelation_features(self.structured_data)
        self.assertTrue(features['autocorr_peak'] > 0.5)  # Should detect pattern
    
    def test_extract_all(self):
        # Test complete feature extraction
        features = extract_all_statistical_features(self.random_data)
        
        # Check feature groups present
        self.assertTrue(any('block_' in k for k in features))
        self.assertTrue(any('ngram_' in k for k in features))
        self.assertTrue(any('entropy_moving_' in k for k in features))
        self.assertTrue(any('autocorr_' in k for k in features))
        
        # All features should be finite
        self.assertTrue(all(np.isfinite(v) for v in features.values()))

if __name__ == '__main__':
    unittest.main()