# Extracts feature data for tls features.
"""
tls_features.py 
TLS protocol-specific feature extraction from encrypted data.
"""

import numpy as np
from typing import Dict,Optional
from collections import Counter


class TLSRecordHeader:
    """TLS Record Layer header parsing."""
    
    RECORD_TYPES = {
        0x14: 'change_cipher_spec',
        0x15: 'alert',
        0x16: 'handshake',
        0x17: 'application_data'
    }
    
    PROTOCOL_VERSIONS = {
        0x0301: 'TLS 1.0',
        0x0302: 'TLS 1.1', 
        0x0303: 'TLS 1.2',
        0x0304: 'TLS 1.3'
    }
    
    @staticmethod
    def parse(data: bytes) -> Optional[Dict[str, any]]:
        """
        Parse TLS Record Layer header.
        
        Args:
            data: Raw bytes starting with TLS record
            
        Returns:
            Dict with parsed header fields or None if invalid
        """
        if len(data) < 5:  # Minimum header size
            return None
            
        try:
            record_type = data[0]
            version = (data[1] << 8) | data[2]
            length = (data[3] << 8) | data[4]
            
            return {
                'type': TLSRecordHeader.RECORD_TYPES.get(record_type, 'unknown'),
                'version': TLSRecordHeader.PROTOCOL_VERSIONS.get(version, 'unknown'),
                'length': length
            }
        except:
            return None


def analyze_record_structure(data: bytes) -> Dict[str, float]:
    """
    Analyze TLS record structure in encrypted data.
    
    Args:
        data: Encrypted data bytes
        
    Returns:
        Dict of record structure features
    """
    features = {
        'record_count': 0,
        'avg_record_size': 0,
        'max_record_size': 0,
        'handshake_ratio': 0,
        'app_data_ratio': 0
    }
    
    # Track record statistics
    records = []
    record_types = Counter()
    
    pos = 0
    while pos < len(data):
        header = TLSRecordHeader.parse(data[pos:])
        if not header:
            break
            
        records.append(header['length'])
        record_types[header['type']] += 1
        pos += 5 + header['length']  # Skip header + content
    
    if records:
        features['record_count'] = len(records)
        features['avg_record_size'] = np.mean(records)
        features['max_record_size'] = max(records)
        
        total = sum(record_types.values())
        features['handshake_ratio'] = record_types['handshake'] / total
        features['app_data_ratio'] = record_types['application_data'] / total
    
    return features


def extract_version_features(data: bytes) -> Dict[str, int]:
    """
    Extract TLS version indicators from encrypted data.
    
    Args:
        data: Encrypted data bytes
        
    Returns:
        Dict of version indicator features
    """
    features = {}
    
    # Look for version bytes in first few records
    versions_seen = set()
    pos = 0
    for _ in range(5):  # Check first 5 records
        if pos >= len(data):
            break
            
        header = TLSRecordHeader.parse(data[pos:])
        if not header:
            break
            
        versions_seen.add(header['version'])
        pos += 5 + header['length']
    
    # Set version indicator features
    for version in TLSRecordHeader.PROTOCOL_VERSIONS.values():
        # Convert "TLS 1.2" to "TLS_1_2"
        version_key = f'version_{version.replace(" ", "_").replace(".", "_")}'
        features[version_key] = 1 if version in versions_seen else 0
    
    return features


def analyze_certificate_patterns(data: bytes) -> Dict[str, float]:
    """
    Analyze potential certificate message patterns.
    
    Args:
        data: Encrypted data bytes
        
    Returns:
        Dict of certificate-related features
    """
    features = {
        'cert_msg_count': 0,
        'avg_cert_size': 0,
        'max_cert_size': 0
    }
    
    # Look for certificate-sized records in handshake sequences
    cert_sizes = []
    pos = 0
    in_handshake = False #this will track if we are in a handshake record, currently set to false
    
    while pos < len(data):
        header = TLSRecordHeader.parse(data[pos:])
        if not header:
            break
            
        if header['type'] == 'handshake':
            in_handshake = True
            if 1024 <= header['length'] <= 4096:  # Typical cert size range
                cert_sizes.append(header['length'])
        else:
            in_handshake = False
            
        pos += 5 + header['length']
    
    if cert_sizes:
        features['cert_msg_count'] = len(cert_sizes)
        features['avg_cert_size'] = np.mean(cert_sizes)
        features['max_cert_size'] = max(cert_sizes)
    
    return features


def extract_cipher_suite_features(data: bytes) -> Dict[str, float]:
    """
    Extract cipher suite related patterns from encrypted data.
    
    Args:
        data: Encrypted data bytes
        
    Returns:
        Dict of cipher suite features
    """
    features = {}
    
    # Common cipher suite patterns to look for
    cipher_patterns = {
        'aes_128_gcm': b'\x13\x02',  # TLS_AES_128_GCM_SHA256
        'aes_256_gcm': b'\x13\x03',  # TLS_AES_256_GCM_SHA384
        'chacha20': b'\x13\x04',     # TLS_CHACHA20_POLY1305_SHA256
        'aes_128_cbc': b'\x00\x2f',  # TLS_RSA_WITH_AES_128_CBC_SHA
        'aes_256_cbc': b'\x00\x35'   # TLS_RSA_WITH_AES_256_CBC_SHA
    }
    
    # Look for cipher patterns in handshake records
    for name, pattern in cipher_patterns.items():
        # Count pattern occurrences in likely cipher suite positions
        count = 0
        pos = 0
        while pos < len(data):
            header = TLSRecordHeader.parse(data[pos:])
            if not header or header['type'] != 'handshake':
                if pos + 2 < len(data):
                    pos += 1
                    continue
                break
                
            record = data[pos+5:pos+5+header['length']]
            count += record.count(pattern)
            pos += 5 + header['length']
        
        features[f'cipher_{name}_freq'] = count
    
    return features


def extract_tls_features(file_path) -> Dict[str, float]:
    """
    Main function to extract TLS features from a file.
    Args:
        file_path: Path to the file to analyze  
    Returns:
        Dict containing all TLS features
    """
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        return extract_all_tls_features(data)
    except Exception as e:
        print(f"Error extracting TLS features from {file_path}: {e}")
        return {}


def extract_tls_features(file_path) -> Dict[str, float]:
    """
    Main function to extract TLS features from a file.
    Args:
        file_path: Path to the file to analyze
    Returns:
        Dict containing all TLS features
    """
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        return extract_all_tls_features(data)
    except Exception as e:
        print(f"Error extracting TLS features from {file_path}: {e}")
        return {}


def extract_all_tls_features(data: bytes) -> Dict[str, float]:
    """
    Extract all TLS protocol features from encrypted data.
    Args:
        data: Encrypted data bytes
    Returns:
        Dict containing all TLS protocol features
    """
    features = {}
    
    # Extract record structure features
    features.update(analyze_record_structure(data))
    
    # Extract version features
    features.update(extract_version_features(data))
    
    # Extract certificate features
    features.update(analyze_certificate_patterns(data))
    
    # Extract cipher suite features
    features.update(extract_cipher_suite_features(data))
    
    return features