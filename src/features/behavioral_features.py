# Extracts feature data for behavioral features.
"""
behavioral_features.py
Behavioral pattern feature extraction from encrypted data.
"""

import numpy as np
from typing import Dict, Optional
from collections import Counter, defaultdict

from .tls_features import TLSRecordHeader


class ConnectionState:
    """Track connection state and transitions."""
    
    STATES = {
        'init': 0,
        'handshake': 1,
        'established': 2,
        'renegotiation': 3,
        'closing': 4,
        'error': 5
    }
    
    def __init__(self):
        self.current_state = 'init'
        self.state_transitions = []
        self.timestamps = []
        
    def transition_to(self, new_state: str, timestamp: float):
        """Record a state transition."""
        if new_state in self.STATES:
            self.state_transitions.append((self.current_state, new_state))
            self.timestamps.append(timestamp)
            self.current_state = new_state
            
    def get_statistics(self) -> Dict[str, float]:
        """Get state transition statistics."""
        features = {}
        
        # Count time spent in each state
        state_times = defaultdict(float)
        for i in range(len(self.state_transitions)):
            state = self.state_transitions[i][1]
            duration = self.timestamps[i+1] - self.timestamps[i] if i+1 < len(self.timestamps) else 0
            state_times[state] += duration
            
        # Add state time features
        total_time = sum(state_times.values())
        if total_time > 0:
            for state, time in state_times.items():
                features[f'state_{state}_ratio'] = time / total_time
                
        # Count specific transitions
        transition_counts = Counter(self.state_transitions)
        features['renegotiation_count'] = sum(1 for t in self.state_transitions 
                                            if t[1] == 'renegotiation')
        features['error_count'] = sum(1 for t in self.state_transitions
                                    if t[1] == 'error')
        
        return features


def analyze_connection_patterns(data: bytes, 
                             metadata: Optional[Dict] = None) -> Dict[str, float]:
    """
    Analyze connection establishment and maintenance patterns.
    
    Args:
        data: Encrypted data bytes
        metadata: Optional metadata with timing information
        
    Returns:
        Dict of connection pattern features
    """
    features = {}
    
    # Initialize state tracking
    state = ConnectionState()
    pos = 0
    timestamp = 0
    handshake_seen = False
    app_data_seen = False
    
    while pos < len(data):
        header = TLSRecordHeader.parse(data[pos:])
        if not header:
            break
            
        # Get timestamp
        if metadata and 'timestamps' in metadata:
            timestamp = metadata['timestamps'].get(pos, timestamp + 0.1)
        else:
            timestamp += 0.1
            
        # Track state transitions based on record types
        if header['type'] == 'handshake' and not handshake_seen:
            state.transition_to('handshake', timestamp)
            handshake_seen = True
        elif header['type'] == 'application_data' and not app_data_seen:
            state.transition_to('established', timestamp)
            app_data_seen = True
        elif header['type'] == 'handshake' and app_data_seen:
            state.transition_to('renegotiation', timestamp)
        elif header['type'] == 'alert':
            state.transition_to('error', timestamp)
            
        pos += 5 + header['length']
        
    # Add closing state if clean shutdown seen
    if pos >= len(data):
        state.transition_to('closing', timestamp)
        
    # Get state statistics
    features.update(state.get_statistics())
    
    return features


def analyze_renegotiation_patterns(data: bytes) -> Dict[str, float]:
    """
    Analyze TLS renegotiation patterns.
    
    Args:
        data: Encrypted data bytes
        
    Returns:
        Dict of renegotiation features
    """
    features = {
        'renego_attempts': 0,
        'renego_success': 0,
        'avg_renego_interval': 0
    }
    
    # Track renegotiation sequences
    renego_times = []
    last_renego = 0
    in_renego = False
    pos = 0
    
    while pos < len(data):
        header = TLSRecordHeader.parse(data[pos:])
        if not header:
            break
            
        if header['type'] == 'handshake':
            if not in_renego:
                features['renego_attempts'] += 1
                if last_renego > 0:
                    renego_times.append(pos - last_renego)
                last_renego = pos
                in_renego = True
        elif header['type'] == 'application_data':
            if in_renego:
                features['renego_success'] += 1
                in_renego = False
                
        pos += 5 + header['length']
        
    # Calculate average interval
    if renego_times:
        features['avg_renego_interval'] = np.mean(renego_times)
        
    return features


def analyze_error_patterns(data: bytes) -> Dict[str, float]:
    """
    Analyze TLS error and alert patterns.
    
    Args:
        data: Encrypted data bytes
        
    Returns:
        Dict of error pattern features
    """
    features = {
        'alert_count': 0,
        'fatal_alert_count': 0,
        'error_burst_count': 0
    }
    
    # Track error patterns
    in_error_burst = False
    error_gap = 0
    pos = 0
    
    while pos < len(data):
        header = TLSRecordHeader.parse(data[pos:])
        if not header:
            break
            
        if header['type'] == 'alert':
            features['alert_count'] += 1
            
            # Check for fatal alerts (approximated by size)
            if header['length'] >= 2:
                features['fatal_alert_count'] += 1
                
            # Track error bursts
            if not in_error_burst:
                features['error_burst_count'] += 1
                in_error_burst = True
            error_gap = 0
        else:
            error_gap += 1
            if error_gap >= 3:  # Reset burst after 3 non-error records
                in_error_burst = False
                
        pos += 5 + header['length']
        
    return features


def analyze_closure_patterns(data: bytes) -> Dict[str, float]:
    """
    Analyze connection closure patterns.
    
    Args:
        data: Encrypted data bytes
        
    Returns:
        Dict of closure pattern features
    """
    features = {
        'clean_closure': 0,
        'abrupt_closure': 0,
        'closure_alert_ratio': 0
    }
    
    # Analyze end of connection
    alert_count = 0
    total_records = 0
    pos = 0
    
    while pos < len(data):
        header = TLSRecordHeader.parse(data[pos:])
        if not header:
            break
            
        total_records += 1
        if header['type'] == 'alert':
            alert_count += 1
            
        pos += 5 + header['length']
        
    # Determine closure type
    if alert_count > 0 and pos >= len(data):
        features['clean_closure'] = 1
    elif pos < len(data):
        features['abrupt_closure'] = 1
        
    if total_records > 0:
        features['closure_alert_ratio'] = alert_count / total_records
        
    return features


def extract_behavioral_features(file_path, metadata=None) -> Dict[str, float]:
    """
    Main function to extract behavioral features from a file.
    
    Args:
        file_path: Path to the file to analyze
        metadata: Optional metadata with timing information
        
    Returns:
        Dict containing all behavioral features
    """
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        return extract_all_behavioral_features(data, metadata)
    except Exception as e:
        print(f"Error extracting behavioral features from {file_path}: {e}")
        return {}


def extract_all_behavioral_features(data: bytes, 
                                 metadata: Optional[Dict] = None) -> Dict[str, float]:
    """
    Extract all behavioral pattern features.
    
    Args:
        data: Encrypted data bytes
        metadata: Optional metadata with timing information
        
    Returns:
        Dict containing all behavioral features
    """
    features = {}
    
    # Extract connection patterns
    features.update(analyze_connection_patterns(data, metadata))
    
    # Extract renegotiation patterns
    features.update(analyze_renegotiation_patterns(data))
    
    # Extract error patterns
    features.update(analyze_error_patterns(data))
    
    # Extract closure patterns
    features.update(analyze_closure_patterns(data))
    
    return features