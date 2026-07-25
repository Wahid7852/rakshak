# Tests models behavior.
#!/usr/bin/env python3
"""Test trained models against available datasets.

This script loads model artifacts from `models/` (joblib files) and runs them on
real data under `data/processed/` if present. If not present, it will synthesize
small deterministic data for smoke testing.

Outputs a JSON report with accuracy, precision, recall, f1, and optional ROC AUC.
"""

import argparse, json
from pathlib import Path
import joblib, numpy as np, pandas as pd
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from typing import Dict, List, Union, Optional

DEFAULT_MODELS_DIR = Path("../models/artifacts")
DEFAULT_DATA_DIR = Path("../data/raw/test")


def load_models(models_dir: Path, model_type='tls'):
    """Load models based on type (tls or flow)"""
    models = {}
    if not models_dir.exists():
        print(f"Models directory {models_dir} not found.\n")
        return models

    # Load global preprocessing components
    scaler = None
    scaler_path = models_dir / 'scaler_large_dataset.pkl'
    if scaler_path.exists():
        try:
            scaler = joblib.load(scaler_path)
            print(f"Loaded global scaler from {scaler_path}")
        except Exception as e:
            print(f"Warning: Failed to load scaler: {e}")

    label_encoder = None
    encoder_path = models_dir / 'label_encoder_large_dataset.pkl'
    if encoder_path.exists():
        try:
            label_encoder = joblib.load(encoder_path)
            print(f"Loaded label encoder from {encoder_path}")
        except Exception as e:
            print(f"Warning: Failed to load label encoder: {e}")

    # Load specific model types
    if model_type == 'tls':
        # Load TLS-specific models
        model_paths = [
            models_dir / 'ensemble/ensemble.joblib',
            models_dir / 'lightgbm/lgb.joblib',
            models_dir / 'neural_net/nn.joblib'
        ]
    else:
        # Load flow-based models
        model_paths = [p for p in models_dir.glob("*.joblib") 
                      if not p.stem.endswith('_preproc') 
                      and p.stem != 'encoders']

    for p in model_paths:
        if p.exists():
            try:
                model_dict = joblib.load(p)
                if isinstance(model_dict, dict):
                    if scaler is not None:
                        model_dict['scaler'] = scaler
                    if label_encoder is not None:
                        model_dict['label_encoder'] = label_encoder
                    models[p.stem] = model_dict
                else:
                    # Raw model - wrap in dict
                    models[p.stem] = {
                        'model': model_dict,
                        'scaler': scaler,
                        'label_encoder': label_encoder
                    }
                print(f"Loaded model from {p}")
            except Exception as e:
                print(f"Failed to load {p}: {e}")

    return models


def load_data(features_path: Optional[Path] = None, labels_path: Optional[Path] = None):
    # If data exists, load it; otherwise synthesize a deterministic dataset
    if features_path and features_path.exists() and labels_path and labels_path.exists():
        X = pd.read_csv(features_path)
        y = pd.read_csv(labels_path)
        # Expect 'file' column and 'family' in labels
        if 'file' in y.columns and 'family' in y.columns:
            # Merge on file/orig_file convention where available
            if 'orig_file' in X.columns:
                df = X.merge(y.rename(columns={'file': 'orig_file'}), on='orig_file', how='left')
            elif 'file' in X.columns:
                df = X.merge(y, on='file', how='left')
            else:
                df = X.copy()
                df['family'] = 'unknown'
        else:
            df = X.copy()
            df['family'] = 'unknown'
    else:
        # Synthesize
        rng = np.random.RandomState(42)
        n = 200
        n_features = 20
        X = pd.DataFrame(rng.randn(n, n_features), columns=[f'f{i}' for i in range(n_features)])
        # Create 3 classes
        y = pd.Series(rng.choice(['A','B','C'], size=n), name='family')
        df = X.copy()
        df['family'] = y

    # Select numeric features
    X = df.select_dtypes(include=[np.number]).fillna(0.0)
    y = df['family'].astype(str).fillna('unknown')
    return X, y




def extract_tls_features(tls_json: Dict) -> Dict[str, float]:
    """Ultra-fast TLS feature extraction - no complex processing.
    Maps raw TLS JSON to numeric features needed by models.
    """
    features = {
        # Direct boolean/numeric fields
        'tls_version_major': int(str(tls_json.get('version', '0.0')).split('.')[0]),
        'tls_version_minor': int(str(tls_json.get('version', '0.0')).split('.')[-1]),
        'is_tls_1_3': 1 if tls_json.get('version') == '1.3' else 0,
        'is_tls_1_2': 1 if tls_json.get('version') == '1.2' else 0,
        'cipher_aes': 1 if 'AES' in (tls_json.get('cipher', '') or '').upper() else 0,
        'cipher_cbc': 1 if 'CBC' in (tls_json.get('cipher', '') or '').upper() else 0,
        'cipher_sha256': 1 if 'SHA256' in (tls_json.get('cipher', '') or '').upper() else 0,
        # Quick numeric extraction
        'cipher_bits': int(tls_json.get('cipher_bits', 0)),
        'cipher_bits_256': 1 if int(tls_json.get('cipher_bits', 0)) == 256 else 0,
        'cipher_bits_128': 1 if int(tls_json.get('cipher_bits', 0)) == 128 else 0,
        'key_exchange_dhe': 1 if 'DHE' in (tls_json.get('key_exchange', '') or '').upper() else 0,
        'key_exchange_rsa': 1 if 'RSA' in (tls_json.get('key_exchange', '') or '').upper() else 0,
        'compression_null': 1 if not tls_json.get('compression') else 0,
        'cert_chain_length': len(tls_json.get('certificates', [])),
        'cert_key_size': int(tls_json.get('cert_key_size', 0)),
        'session_ticket_lifetime': int(tls_json.get('ticket_lifetime_hint', 0)),
        'session_reuse': 1 if tls_json.get('session_reused') else 0,
        # Quick calculations
        'alpn_count': len(tls_json.get('alpn', [])),
        'extension_count': len(tls_json.get('extensions', [])),
        'extension_entropy': float(len(tls_json.get('extensions', []))),  # simple proxy
        'sni_present': 1 if tls_json.get('sni') else 0,
        'ocsp_stapling': 1 if tls_json.get('ocsp_stapling') else 0,
        'heartbeat_enabled': 1 if tls_json.get('heartbeat') else 0,
        # File/flow features
        'file_size': int(tls_json.get('size', 0)),
        'file_permissions': int(tls_json.get('permissions', 0)),
        'is_system_path': 1 if any(p in str(tls_json.get('path', '')) for p in ['/usr', '/bin', '/sbin', '/etc', '/var']) else 0,
        'session_entropy': float(len(tls_json.get('session_id', ''))) / 32.0,  # normalize
        'session_id_length': len(tls_json.get('session_id', '')),
        'timestamp': int(tls_json.get('timestamp', 0)),
        # Encryption mode features
        'encryption_mode_cbc': 1 if 'CBC' in (tls_json.get('encryption_mode', '') or '').upper() else 0,
        'encryption_mode_gcm': 1 if 'GCM' in (tls_json.get('encryption_mode', '') or '').upper() else 0,
        'key_mode_per_file': 1 if tls_json.get('key_per_file') else 0,
        'mac_entropy': float(len(tls_json.get('mac', ''))) / 32.0,  # normalize
        'mac_length': len(tls_json.get('mac', '')),
    }
    return features


def extract_flow_features(flow_json: Dict) -> Dict[str, float]:
    """Ultra-fast network flow feature extraction.
    Maps raw flow JSON to numeric features needed by models.
    """
    features = {
        'dur': float(flow_json.get('duration', 0)),
        'proto': hash(str(flow_json.get('protocol', ''))) % 100,  # simple hash
        'service': hash(str(flow_json.get('service', ''))) % 100,
        'state': hash(str(flow_json.get('state', ''))) % 100,
        'spkts': int(flow_json.get('src_packets', 0)),
        'dpkts': int(flow_json.get('dst_packets', 0)),
        'sbytes': int(flow_json.get('src_bytes', 0)),
        'dbytes': int(flow_json.get('dst_bytes', 0)),
        'rate': float(flow_json.get('rate', 0)),
        'sttl': int(flow_json.get('src_ttl', 0)),
        'dttl': int(flow_json.get('dst_ttl', 0)),
        'sload': float(flow_json.get('src_load', 0)),
        'dload': float(flow_json.get('dst_load', 0)),
        'sloss': int(flow_json.get('src_loss', 0)),
        'dloss': int(flow_json.get('dst_loss', 0)),
        'sinpkt': float(flow_json.get('src_inter_packet_time', 0)),
        'dinpkt': float(flow_json.get('dst_inter_packet_time', 0)),
        'sjit': float(flow_json.get('src_jitter', 0)),
        'djit': float(flow_json.get('dst_jitter', 0)),
        'swin': int(flow_json.get('src_window', 0)),
        'stcpb': int(flow_json.get('src_tcp_base', 0)),
        'dtcpb': int(flow_json.get('dst_tcp_base', 0)),
        'dwin': int(flow_json.get('dst_window', 0)),
        'tcprtt': float(flow_json.get('tcp_rtt', 0)),
        'synack': float(flow_json.get('syn_ack_time', 0)),
        'ackdat': float(flow_json.get('ack_data_time', 0)),
        'smean': float(flow_json.get('src_mean_size', 0)),
        'dmean': float(flow_json.get('dst_mean_size', 0)),
        'trans_depth': int(flow_json.get('transaction_depth', 0)),
        'response_body_len': int(flow_json.get('response_size', 0)),
        'ct_srv_src': int(flow_json.get('conn_count_srv_src', 0)),
        'ct_state_ttl': int(flow_json.get('conn_count_state_ttl', 0)),
        'ct_dst_ltm': int(flow_json.get('conn_count_dst_ltm', 0)),
        'ct_src_dport_ltm': int(flow_json.get('conn_count_src_dport', 0)),
        'ct_dst_sport_ltm': int(flow_json.get('conn_count_dst_sport', 0)),
        'ct_dst_src_ltm': int(flow_json.get('conn_count_dst_src', 0)),
        'is_ftp_login': 1 if flow_json.get('is_ftp_login') else 0,
        'ct_ftp_cmd': int(flow_json.get('ftp_command_count', 0)),
        'ct_flw_http_mthd': int(flow_json.get('http_method_count', 0)),
        'ct_src_ltm': int(flow_json.get('conn_count_src', 0)),
        'ct_srv_dst': int(flow_json.get('conn_count_srv_dst', 0)),
        'is_sm_ips_ports': 1 if flow_json.get('is_same_ips_ports') else 0
    }
    return features


def detect_json_type(json_obj: Dict) -> str:
    """Quickly detect if a JSON object is TLS, flow, or preprocessed features."""
    if any(k in json_obj for k in ['tls_version_major', 'cipher_bits', 'extension_count']):
        return 'tls_features'
    if any(k in json_obj for k in ['version', 'cipher', 'extensions']):
        return 'tls_raw'
    if any(k in json_obj for k in ['dur', 'proto', 'spkts', 'dpkts']):
        return 'flow_features'
    if any(k in json_obj for k in ['duration', 'protocol', 'src_packets']):
        return 'flow_raw'
    return 'unknown'


def load_data_from_json(json_path: Path):
    """Load dataset from a JSON file. Supported formats:
    - List of records [{feat1:..., featN:..., 'family': label}, ...]
    - {'features': [...], 'labels': [...]} where features is list of records
    - {'rows': [...]} where each row includes the label field 'family' or 'label'
    - Raw TLS/flow JSON records (will be preprocessed)
    """
    data = json.loads(json_path.read_text())
    if isinstance(data, list):
        # Process list of records
        records = []
        for record in data:
            json_type = detect_json_type(record)
            if json_type == 'tls_raw':
                features = extract_tls_features(record)
            elif json_type == 'flow_raw':
                features = extract_flow_features(record)
            else:
                features = record  # already feature dict
            features['family'] = record.get('label', 'unknown')
            records.append(features)
        df = pd.DataFrame(records)
    elif isinstance(data, dict):
        if 'features' in data and 'labels' in data:
            # Process feature array + labels
            features = []
            for feat in data['features']:
                json_type = detect_json_type(feat)
                if json_type == 'tls_raw':
                    features.append(extract_tls_features(feat))
                elif json_type == 'flow_raw':
                    features.append(extract_flow_features(feat))
                else:
                    features.append(feat)
            X = pd.DataFrame(features)
            y = pd.Series(data['labels'], name='family')
            # ensure same length
            df = X.copy()
            df['family'] = y
        elif 'rows' in data:
            # Process rows array
            records = []
            for record in data['rows']:
                json_type = detect_json_type(record)
                if json_type == 'tls_raw':
                    features = extract_tls_features(record)
                elif json_type == 'flow_raw':
                    features = extract_flow_features(record)
                else:
                    features = record
                features['family'] = record.get('label', 'unknown')
                records.append(features)
            df = pd.DataFrame(records)
        else:
            # try to coerce dict-of-lists into DataFrame
            try:
                df = pd.DataFrame(data)
            except Exception:
                raise ValueError(f"Unsupported JSON structure in {json_path}")
    else:
        raise ValueError(f"Unsupported JSON root type in {json_path}")

    # If no explicit label column, try common names
    if 'family' not in df.columns and 'label' in df.columns:
        df['family'] = df['label']
    if 'family' not in df.columns and 'y' in df.columns:
        df['family'] = df['y']

    X = df.select_dtypes(include=[np.number]).fillna(0.0)
    y = df['family'].astype(str).fillna('unknown')
    return X, y


def load_model_artifact(name: str, artifacts_dir: Optional[Path] = None) -> dict:
    """Load a model artifact and its associated preprocessor/encoder if available."""
    if artifacts_dir is None:
        artifacts_dir = Path(DEFAULT_MODELS_DIR)
    
    result = {}
    
    # Load main model artifact
    model_path = artifacts_dir / f"{name}.joblib"
    if not model_path.exists():
        return {'error': f"Model file {name}.joblib not found"}
    
    try:
        artifact = joblib.load(model_path)
        if isinstance(artifact, dict):
            result.update(artifact)
        else:
            result['model'] = artifact
    except Exception as e:
        return {'error': f"Failed to load model {name}: {str(e)}"}

    # Try to load associated preprocessor
    preproc_path = artifacts_dir / f"{name}_preproc.joblib"
    if preproc_path.exists():
        try:
            preproc = joblib.load(preproc_path)
            if isinstance(preproc, dict):
                result['preprocessor'] = preproc.get('model') or preproc.get('preprocessor')
                if 'cols' in preproc and 'cols' not in result:
                    result['cols'] = preproc['cols']
            else:
                result['preprocessor'] = preproc
        except Exception as e:
            print(f"Warning: Failed to load preprocessor for {name}: {e}")

    # If no columns specified, try model_meta.json
    if 'cols' not in result:
        meta_path = artifacts_dir / 'model_meta.json'
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                if 'features' in meta:
                    result['cols'] = meta['features']
            except Exception:
                pass

    return result




def extract_quantum_features(X: pd.DataFrame, n_qubits: int = 6) -> np.ndarray:
    """Extract quantum features using ZZ-feature map."""
    # Import QuantumFeatureMap from service module
    from service.feature_map import QuantumFeatureMap
    
    # Create feature map with default ZZ architecture
    qmap = QuantumFeatureMap(n_wires=n_qubits, arch_type="zz", shots=None)
    
    # Extract numeric features and normalize
    X_num = X.select_dtypes(include=["number"]).astype(float)
    if "proto" in X.columns:
        X_num["proto"] = X["proto"].astype(str).map({"tcp": 0.0, "udp": 1.0, "icmp": 2.0}).fillna(0.0)
        
    # Normalize features to [-1,1] range
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_num)
    
    # Apply quantum feature map row by row
    X_quantum = np.array([qmap(x) for x in X_scaled])
    return X_quantum

def hybrid_predict(X: pd.DataFrame, artifacts: dict) -> tuple:
    """Two-stage prediction: neural net first, quantum for uncertain cases"""
    nn_artifact = artifacts.get('neural_net')
    qsvm_artifact = artifacts.get('qsvc')
    
    if nn_artifact is None or qsvm_artifact is None:
        return None, 0.0
        
    # 1. Try neural net first (fast path)
    try:
        nn_model = nn_artifact.get('model')
        nn_cols = nn_artifact.get('cols', [])
        if nn_cols:
            X_nn = X[nn_cols].copy()
            if "proto" in X_nn.columns:
                X_nn["proto"] = X_nn["proto"].astype(str).map({"tcp": 0.0, "udp": 1.0, "icmp": 2.0}).fillna(0.0)
            X_nn = X_nn.select_dtypes(include=["number"])
        else:
            X_nn = X
            
        nn_preprocessor = nn_artifact.get('preprocessor')
        if nn_preprocessor:
            X_nn = nn_preprocessor.transform(X_nn)
            
        if hasattr(nn_model, 'predict_proba'):
            proba = nn_model.predict_proba(X_nn)
            confidence = np.max(proba, axis=1)
            if np.any(confidence > 0.95):
                return nn_model.predict(X_nn), float(confidence.max())
    except Exception:
        pass
        
    # 2. For uncertain cases, use quantum model
    try:
        qsvm_cols = qsvm_artifact.get('cols', [])
        X_quantum = extract_quantum_features(X[qsvm_cols] if qsvm_cols else X)
        qsvm_model = qsvm_artifact.get('model')
        prediction = qsvm_model.predict(X_quantum)
        return prediction, 1.0  # Trust quantum model's decision
    except Exception:
        return None, 0.0

def evaluate_model_artifact(artifact, X: pd.DataFrame, y_true: pd.Series):
    """Evaluate a model artifact (with optional preprocessor) on input data."""
    # Extract components
    model = artifact.get('model')
    preprocessor = artifact.get('preprocessor')
    cols = artifact.get('cols')
    label_encoder = artifact.get('label_encoder')
    model_type = artifact.get('type', 'classical')  # 'classical', 'quantum', or 'neural'
    
    if model is None:
        return {'error': "No model found in artifact"}

    # Align features if cols specified
    if cols is not None:
        try:
            X = X.reindex(columns=cols, fill_value=0.0)
        except Exception as e:
            return {'error': f"Failed to align features: {str(e)}"}

    # Apply preprocessor if available
    X_processed = X
    if preprocessor is not None:
        try:
            X_processed = pd.DataFrame(
                preprocessor.transform(X), 
                columns=X.columns, 
                index=X.index
            )
        except Exception as e:
            # Fall back to raw features
            print(f"Warning: Preprocessor failed: {e}")

    # Encode labels if encoder available
    y_encoded = y_true
    if label_encoder is not None:
        try:
            y_encoded = label_encoder.transform(y_true.astype(str))
        except Exception as e:
            print(f"Warning: Label encoding failed: {e}")

    # Predictions
    try:
        y_pred = model.predict(X_processed)
    except Exception as e:
        return {'error': str(e)}

    # Compute metrics
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, average='weighted', zero_division=0)
    rec = recall_score(y_true, y_pred, average='weighted', zero_division=0)
    f1 = f1_score(y_true, y_pred, average='weighted', zero_division=0)

    return {
        'accuracy': float(acc),
        'precision': float(prec),
        'recall': float(rec),
        'f1': float(f1)
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--models-dir', default=str(DEFAULT_MODELS_DIR))
    p.add_argument('--features', default=str(DEFAULT_DATA_DIR / 'features.csv'))
    p.add_argument('--labels', default=str(DEFAULT_DATA_DIR / 'labels.csv'))
    p.add_argument('--json-input', default=None, help="Path to JSON file with raw or preprocessed data")
    p.add_argument('--out', default='model_test_report.json')
    args = p.parse_args()

    models = load_models(Path(args.models_dir))
    X, y = load_data(Path(args.features), Path(args.labels))

    # If models include a 'label_encoder' saved into artifact, use that mapping
    label_encoder = None
    if models:
        # Try to extract a label encoder from the first artifact if present
        first = next(iter(models.values()))
        if isinstance(first, dict) and 'label_encoder' in first:
            label_encoder = first['label_encoder']

    # If y are strings and models expect encoded ints, encode with label_encoder inferred from saved artifact
    y_labels = y
    if label_encoder is not None and hasattr(label_encoder, 'transform'):
        try:
            y_labels = label_encoder.transform(y.astype(str))
        except Exception:
            # fallback
            pass

    # Try to load global encoders/scalers
    encoders_path = Path('../models/artifacts/encoders.joblib')
    if encoders_path.exists():
        try:
            encoders = joblib.load(encoders_path)
            if isinstance(encoders, dict):
                if 'scaler' in encoders:
                    print("Found global scaler")
                if 'encoders' in encoders:
                    print("Found global categorical encoders")
        except Exception as e:
            print(f"Warning: Failed to load global encoders: {e}")

    # Load and evaluate each model
    report = {}
    model_files = list(Path(args.models_dir).glob('*.joblib'))
    for model_path in model_files:
        name = model_path.stem
        if name.endswith('_preproc') or name == 'encoders':
            continue
        
        try:
            # Load model with its preprocessor
            artifact = load_model_artifact(name, Path(args.models_dir))
            if 'error' in artifact:
                report[name] = artifact
                continue

            # Add label encoder if available
            if label_encoder is not None:
                artifact['label_encoder'] = label_encoder

            # Evaluate
            result = evaluate_model_artifact(artifact, X, y_labels)
            report[name] = result
        except Exception as e:
            report[name] = {'error': str(e)}

            # Note: Redundant code block removed since this logic is already in evaluate_model_artifact

    with open(args.out, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"Wrote report to {args.out}")


if __name__ == '__main__':
    main()

