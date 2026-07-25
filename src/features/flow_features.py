# Extracts feature data for flow features.
"""
flow_features.py
Flow and timing feature extraction from encrypted data.
"""

import numpy as np
from typing import Dict, List, Tuple, Optional


from .tls_features import TLSRecordHeader


class FlowMetrics:
    """Track metrics for flows in each direction."""
    
    def __init__(self):
        self.packet_sizes = []
        self.inter_arrival_times = []
        self.bytes_count = 0
        self.packet_count = 0
        self.last_time = 0
        
    def add_packet(self, size: int, timestamp: float):
        """Add a packet and update metrics."""
        self.packet_sizes.append(size)
        self.bytes_count += size
        self.packet_count += 1
        
        if self.last_time > 0:
            self.inter_arrival_times.append(timestamp - self.last_time)
        self.last_time = timestamp
        
    def get_statistics(self, prefix: str = '') -> Dict[str, float]:
        """Get statistical features for this flow direction."""
        features = {}
        
        # Packet size statistics
        if self.packet_sizes:
            features[f'{prefix}pkt_size_mean'] = np.mean(self.packet_sizes)
            features[f'{prefix}pkt_size_std'] = np.std(self.packet_sizes)
            features[f'{prefix}pkt_size_max'] = max(self.packet_sizes)
            features[f'{prefix}pkt_size_min'] = min(self.packet_sizes)
            
        # Timing statistics
        if self.inter_arrival_times:
            features[f'{prefix}iat_mean'] = np.mean(self.inter_arrival_times)
            features[f'{prefix}iat_std'] = np.std(self.inter_arrival_times)
            features[f'{prefix}iat_max'] = max(self.inter_arrival_times)
            
        # Counter statistics
        features[f'{prefix}bytes'] = self.bytes_count
        features[f'{prefix}packets'] = self.packet_count
        
        return features


def analyze_flow_sizes(data: bytes) -> Dict[str, float]:
    """
    Analyze message size patterns in the flow.
    
    Args:
        data: Encrypted data bytes
        
    Returns:
        Dict of size-based features
    """
    features = {}
    
    # Record sizes sequence
    sizes = []
    pos = 0
    
    while pos < len(data):
        header = TLSRecordHeader.parse(data[pos:])
        if not header:
            break
            
        sizes.append(header['length'])
        pos += 5 + header['length']
        
    if sizes:
        # Basic statistics
        features['flow_size_mean'] = np.mean(sizes)
        features['flow_size_std'] = np.std(sizes)
        features['flow_size_max'] = max(sizes)
        features['flow_size_min'] = min(sizes)
        
        # Size transition patterns
        size_ratios = []
        for i in range(len(sizes)-1):
            if sizes[i] > 0:
                size_ratios.append(sizes[i+1] / sizes[i])
        
        if size_ratios:
            features['size_ratio_mean'] = np.mean(size_ratios)
            features['size_ratio_std'] = np.std(size_ratios)
    
    return features


def extract_timing_patterns(data: bytes, 
                          metadata: Optional[Dict] = None) -> Dict[str, float]:
    """
    Extract timing-related patterns from flow.
    
    Args:
        data: Encrypted data bytes
        metadata: Optional metadata with timing information
        
    Returns:
        Dict of timing pattern features
    """
    features = {}
    
    # Initialize flow tracking
    inbound = FlowMetrics()
    outbound = FlowMetrics()
    
    pos = 0
    timestamp = 0
    
    while pos < len(data):
        header = TLSRecordHeader.parse(data[pos:])
        if not header:
            break
            
        # Use metadata timing if available, otherwise estimate
        if metadata and 'timestamps' in metadata:
            timestamp = metadata['timestamps'].get(pos, timestamp + 0.1)
        else:
            timestamp += 0.1  # Rough estimate
            
        # Track flows by direction based on record type
        if header['type'] in ['handshake', 'application_data']:
            if header['type'] == 'handshake':
                inbound.add_packet(header['length'], timestamp)
            else:
                outbound.add_packet(header['length'], timestamp)
                
        pos += 5 + header['length']
    
    # Add directional statistics
    features.update(inbound.get_statistics('inbound_'))
    features.update(outbound.get_statistics('outbound_'))
    
    # Add ratio features
    if inbound.bytes_count > 0 and outbound.bytes_count > 0:
        features['bytes_ratio'] = outbound.bytes_count / inbound.bytes_count
        features['packet_ratio'] = outbound.packet_count / inbound.packet_count
    
    return features


def analyze_burst_patterns(data: bytes) -> Dict[str, float]:
    """
    Analyze traffic burst patterns.
    
    Args:
        data: Encrypted data bytes
        
    Returns:
        Dict of burst pattern features
    """
    features = {}
    
    # Track bursts
    burst_sizes = []
    current_burst = 0
    burst_threshold = 0.5  # seconds
    last_time = 0
    pos = 0
    
    while pos < len(data):
        header = TLSRecordHeader.parse(data[pos:])
        if not header:
            break
            
        # Estimate timing (could be from metadata)
        time_delta = 0.1  # Rough estimate
        
        if last_time > 0 and time_delta > burst_threshold:
            if current_burst > 0:
                burst_sizes.append(current_burst)
                current_burst = 0
        
        current_burst += header['length']
        last_time += time_delta
        pos += 5 + header['length']
    
    # Add final burst
    if current_burst > 0:
        burst_sizes.append(current_burst)
    
    if burst_sizes:
        features['burst_count'] = len(burst_sizes)
        features['burst_size_mean'] = np.mean(burst_sizes)
        features['burst_size_std'] = np.std(burst_sizes)
        features['burst_size_max'] = max(burst_sizes)
    
    return features


def analyze_flow_duration(data: bytes, 
                        metadata: Optional[Dict] = None) -> Dict[str, float]:
    """
    Analyze flow duration and rate features.
    
    Args:
        data: Encrypted data bytes
        metadata: Optional metadata with timing information
        
    Returns:
        Dict of duration-based features
    """
    features = {}
    
    # If metadata has timestamps, use them directly
    if metadata and 'timestamps' in metadata:
        timestamps = list(metadata['timestamps'].values())
        if len(timestamps) > 1:
            duration = max(timestamps) - min(timestamps)
            features['flow_duration'] = duration
            
            # Calculate rates using actual duration
            total_bytes = len(data)
            packet_count = len(metadata['timestamps'])
            
            if duration > 0:
                features['bytes_per_second'] = total_bytes / duration
                features['packets_per_second'] = packet_count / duration
            
            return features
    
    # Fallback to parsing if no metadata available
    first_time = 0
    last_time = 0
    total_bytes = 0
    pos = 0
    
    while pos < len(data):
        header = TLSRecordHeader.parse(data[pos:])
        if not header:
            break
            
        # Use metadata timing if available
        if metadata and 'timestamps' in metadata:
            timestamp = metadata['timestamps'].get(pos, last_time + 0.1)
        else:
            timestamp = last_time + 0.1
            
        if first_time == 0:
            first_time = timestamp
        last_time = timestamp
        
        total_bytes += header['length']
        pos += 5 + header['length']
    
    duration = last_time - first_time
    if duration > 0:
        features['flow_duration'] = duration
        features['bytes_per_second'] = total_bytes / duration
        features['packets_per_second'] = pos / (5 * duration)  # Approximate packet count
    
    return features


def extract_flow_features(file_path, metadata=None) -> Dict[str, float]:
    """
    Main function to extract flow features from a file.
    
    Args:
        file_path: Path to the file to analyze
        metadata: Optional metadata with timing information
        
    Returns:
        Dict containing all flow features
    """
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        return extract_all_flow_features(data, metadata)
    except Exception as e:
        print(f"Error extracting flow features from {file_path}: {e}")
        return {}


def extract_all_flow_features(data: bytes, 
                            metadata: Optional[Dict] = None) -> Dict[str, float]:
    """
    Extract all flow and timing features.
    
    Args:
        data: Encrypted data bytes
        metadata: Optional metadata with timing information
        
    Returns:
        Dict containing all flow/timing features
    """
    features = {}
    
    # Extract size-based features
    features.update(analyze_flow_sizes(data))
    
    # Extract timing patterns
    features.update(extract_timing_patterns(data, metadata))
    
    # Extract burst patterns
    features.update(analyze_burst_patterns(data))
    
    # Extract duration features
    features.update(analyze_flow_duration(data, metadata))
    
    return features