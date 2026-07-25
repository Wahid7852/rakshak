# Tests behavioral features behavior.
"""
Test cases for behavioral feature extraction.
"""

import os, sys, unittest, numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.features.behavioral_features import *


class TestBehavioralFeatures(unittest.TestCase):
    
    def setUp(self):
        # Create test connection data
        self.records = []
        
        # Initial handshake sequence
        self.records.extend([
            # ClientHello
            b'\x16\x03\x03\x00\x40' + b'A' * 64,
            # ServerHello
            b'\x16\x03\x03\x00\x30' + b'B' * 48,
            # Certificate
            b'\x16\x03\x03\x02\x00' + b'C' * 512
        ])
        
        # Application data
        self.records.extend([
            b'\x17\x03\x03\x00\x20' + b'D' * 32,
            b'\x17\x03\x03\x00\x40' + b'E' * 64
        ])
        
        # Renegotiation
        self.records.extend([
            b'\x16\x03\x03\x00\x20' + b'F' * 32,
            b'\x16\x03\x03\x00\x30' + b'G' * 48
        ])
        
        # Error/Alert
        self.records.append(b'\x15\x03\x03\x00\x02' + b'H' * 2)
        
        # Closing sequence
        self.records.extend([
            b'\x15\x03\x03\x00\x02' + b'I' * 2,
            b'\x15\x03\x03\x00\x02' + b'J' * 2
        ])
        
        # Combine records
        self.test_data = b''.join(self.records)
        
        # Sample metadata
        self.metadata = {
            'timestamps': {i*100: i*0.1 for i in range(10)}
        }
        
    def test_connection_state(self):
        state = ConnectionState()
        
        # Test state transitions
        state.transition_to('handshake', 0.1)
        state.transition_to('established', 0.2)
        state.transition_to('renegotiation', 0.3)
        
        stats = state.get_statistics()
        
        self.assertTrue('state_handshake_ratio' in stats)
        self.assertTrue('renegotiation_count' in stats)
        self.assertEqual(stats['renegotiation_count'], 1)
        
    def test_connection_pattern_analysis(self):
        features = analyze_connection_patterns(self.test_data, self.metadata)
        
        self.assertTrue('state_handshake_ratio' in features)
        self.assertTrue('state_established_ratio' in features)
        self.assertTrue('renegotiation_count' in features)
        self.assertTrue('error_count' in features)
        
    def test_renegotiation_pattern_analysis(self):
        features = analyze_renegotiation_patterns(self.test_data)
        
        self.assertTrue(features['renego_attempts'] > 0)
        self.assertTrue('avg_renego_interval' in features)
        
    def test_error_pattern_analysis(self):
        features = analyze_error_patterns(self.test_data)
        
        self.assertTrue(features['alert_count'] > 0)
        self.assertTrue('error_burst_count' in features)
        
    def test_closure_pattern_analysis(self):
        # Test clean closure
        features = analyze_closure_patterns(self.test_data)
        
        self.assertEqual(features['clean_closure'], 1)
        self.assertEqual(features['abrupt_closure'], 0)
        self.assertTrue(features['closure_alert_ratio'] > 0)
        
        # Test abrupt closure
        truncated_data = self.test_data[:-10]  # Remove closing sequence
        features = analyze_closure_patterns(truncated_data)
        
        self.assertEqual(features['clean_closure'], 0)
        self.assertEqual(features['abrupt_closure'], 1)
        
    def test_all_behavioral_features_extraction(self):
        features = extract_all_behavioral_features(self.test_data, self.metadata)
        
        # Check all feature groups present
        self.assertTrue(any('state_' in k for k in features))
        self.assertTrue(any('renego_' in k for k in features))
        self.assertTrue(any('alert_' in k for k in features))
        self.assertTrue('clean_closure' in features)
        
        # All features should be finite
        self.assertTrue(all(np.isfinite(v) for v in features.values()))


if __name__ == '__main__':
    unittest.main()