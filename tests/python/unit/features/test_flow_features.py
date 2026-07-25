# Tests flow features behavior.
"""
Test cases for flow and timing feature extraction.
"""

import os, sys, unittest, numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.features.flow_features import *


class TestFlowFeatures(unittest.TestCase):
    
    def setUp(self):
        # Create simulated flow data with multiple records
        self.records = []
        
        # Add handshake records
        for size in [128, 256, 512]:
            self.records.append(
                b'\x16'  # Type: Handshake
                + b'\x03\x03'  # Version: TLS 1.2
                + size.to_bytes(2, byteorder='big')  # Length
                + b'A' * size  # Content
            )
            
        # Add application data records
        for size in [64, 128, 256]:
            self.records.append(
                b'\x17'  # Type: Application Data
                + b'\x03\x03'  # Version: TLS 1.2
                + size.to_bytes(2, byteorder='big')  # Length
                + b'B' * size  # Content
            )
            
        # Combine records
        self.test_data = b''.join(self.records)
        
        # Create sample metadata with timestamps
        self.metadata = {
            'timestamps': {
                0: 0.0,
                133: 0.1,
                389: 0.3,
                901: 0.5,
                970: 0.7,
                1103: 0.9,
                1364: 1.1
            }
        }
        
    def test_flow_metrics(self):
        metrics = FlowMetrics()
        
        # Add some test packets
        metrics.add_packet(100, 0.1)
        metrics.add_packet(200, 0.3)
        metrics.add_packet(150, 0.6)
        
        stats = metrics.get_statistics('test_')
        
        self.assertEqual(stats['test_bytes'], 450)
        self.assertEqual(stats['test_packets'], 3)
        self.assertEqual(stats['test_pkt_size_mean'], 150)
        
    def test_flow_size_analysis(self):
        features = analyze_flow_sizes(self.test_data)
        
        self.assertTrue('flow_size_mean' in features)
        self.assertTrue('flow_size_std' in features)
        self.assertEqual(features['flow_size_max'], 512)
        self.assertEqual(features['flow_size_min'], 64)
        
    def test_timing_pattern_extraction(self):
        features = extract_timing_patterns(self.test_data, self.metadata)
        
        self.assertTrue('inbound_bytes' in features)
        self.assertTrue('outbound_bytes' in features)
        self.assertTrue('bytes_ratio' in features)
        
        # Verify directionality
        self.assertTrue(features['inbound_bytes'] > 0)
        self.assertTrue(features['outbound_bytes'] > 0)
        
    def test_burst_pattern_analysis(self):
        features = analyze_burst_patterns(self.test_data)
        
        self.assertTrue('burst_count' in features)
        self.assertTrue('burst_size_mean' in features)
        self.assertTrue(features['burst_count'] > 0)
        
    def test_flow_duration_analysis(self):
        features = analyze_flow_duration(self.test_data, self.metadata)
        
        self.assertTrue('flow_duration' in features)
        self.assertTrue('bytes_per_second' in features)
        self.assertTrue('packets_per_second' in features)
        
        # Duration should match metadata
        self.assertAlmostEqual(features['flow_duration'], 1.1, places=1)
        
    def test_all_flow_features_extraction(self):
        features = extract_all_flow_features(self.test_data, self.metadata)
        
        # Check all feature groups present
        self.assertTrue(any('flow_size' in k for k in features))
        self.assertTrue(any('inbound_' in k for k in features))
        self.assertTrue(any('outbound_' in k for k in features))
        self.assertTrue(any('burst_' in k for k in features))
        
        # All features should be finite
        self.assertTrue(all(np.isfinite(v) for v in features.values()))
        

if __name__ == '__main__':
    unittest.main()