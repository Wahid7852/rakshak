# Tests tls features behavior.
"""
Test cases for TLS protocol feature extraction.
"""

import os, sys, unittest, numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.features.tls_features import *

class TestTLSFeatures(unittest.TestCase):
    
    def setUp(self):
        # Create simulated TLS record data
        self.handshake_record = (
            b'\x16'  # Type: Handshake
            + b'\x03\x03'  # Version: TLS 1.2
            + b'\x00\x50'  # Length: 80 bytes
            + b'A' * 80  # Simulated content
        )
        
        self.app_data_record = (
            b'\x17'  # Type: Application Data
            + b'\x03\x03'  # Version: TLS 1.2  
            + b'\x00\x20'  # Length: 32 bytes
            + b'B' * 32  # Simulated content
        )
        
        # Combine records
        self.test_data = self.handshake_record + self.app_data_record
        
    def test_record_header_parsing(self):
        header = TLSRecordHeader.parse(self.handshake_record)
        self.assertEqual(header['type'], 'handshake')
        self.assertEqual(header['version'], 'TLS 1.2')
        self.assertEqual(header['length'], 80)
        
    def test_record_structure_analysis(self):
        features = analyze_record_structure(self.test_data)
        
        self.assertEqual(features['record_count'], 2)
        self.assertEqual(features['handshake_ratio'], 0.5)
        self.assertEqual(features['app_data_ratio'], 0.5)
        self.assertEqual(features['max_record_size'], 80)
        
    def test_version_features(self):
        features = extract_version_features(self.test_data)
        
        self.assertEqual(features['version_TLS_1_2'], 1)
        self.assertEqual(features['version_TLS_1_3'], 0)
        
    def test_certificate_pattern_analysis(self):
        # Create record with certificate-sized content
        cert_record = (
            b'\x16'  # Type: Handshake
            b'\x03\x03'  # Version: TLS 1.2
            b'\x04\x00'  # Length: 1024 bytes
            b'C' * 1024  # Simulated certificate
        )
        
        features = analyze_certificate_patterns(cert_record)
        self.assertEqual(features['cert_msg_count'], 1)
        self.assertEqual(features['max_cert_size'], 1024)
        
    def test_cipher_suite_features(self):
        # Create record with cipher suite pattern
        cipher_record = (
            b'\x16'  # Type: Handshake 
            b'\x03\x03'  # Version: TLS 1.2
            b'\x00\x06'  # Length: 6 bytes
            b'\x13\x02'  # AES 128 GCM pattern
            b'DD'  # Padding
        )
        
        features = extract_cipher_suite_features(cipher_record)
        self.assertEqual(features['cipher_aes_128_gcm_freq'], 1)
        
    def test_all_features_extraction(self):
        features = extract_all_tls_features(self.test_data)
        
        # Check all feature groups present
        self.assertTrue(any('record_' in k for k in features))
        self.assertTrue(any('version_' in k for k in features))
        self.assertTrue(any('cert_' in k for k in features))
        self.assertTrue(any('cipher_' in k for k in features))
        
        # All features should be finite
        self.assertTrue(all(np.isfinite(v) for v in features.values()))

if __name__ == '__main__':
    unittest.main()