# Configuration Guide

## Overview
This guide covers the configuration options available for the TLS-based malware classification system.

## Configuration Files

### 1. Feature Configuration (configs/feature_configs.yaml)
```yaml
feature_extraction:
  # TLS Feature Settings
  tls:
    enabled: true
    max_handshake_size: 1024
    include_extensions: true
    certificate_analysis: true
    
  # Statistical Feature Settings
  statistical:
    enabled: true
    block_size: 256
    use_entropy: true
    byte_frequency: true
    
  # Behavioral Feature Settings
  behavioral:
    enabled: true
    sequence_length: 100
    api_call_tracking: true
    system_call_tracking: true
    
  # Flow Feature Settings
  flow:
    enabled: true
    max_packets: 1000
    include_timing: true
    direction_analysis: true

preprocessing:
  # Data Cleaning Settings
  cleaning:
    remove_constant: true
    remove_correlated: true
    correlation_threshold: 0.95
    handle_missing: true
    
  # Scaling Settings
  scaling:
    method: "standard"  # or "minmax", "robust"
    with_mean: true
    with_std: true
```

### 2. Model Configuration (configs/model_configs.yaml)
```yaml
# Random Forest Configuration
random_forest:
  n_estimators: 100
  max_depth: null
  min_samples_split: 2
  min_samples_leaf: 1
  max_features: "sqrt"
  class_weight: "balanced"

# XGBoost Configuration
xgboost:
  n_estimators: 100
  max_depth: 6
  learning_rate: 0.3
  min_child_weight: 1
  subsample: 0.8
  colsample_bytree: 0.8
  gamma: 0

# LightGBM Configuration
lightgbm:
  n_estimators: 100
  max_depth: -1
  learning_rate: 0.3
  num_leaves: 31
  min_data_in_leaf: 20
  feature_fraction: 0.8
  bagging_fraction: 0.8
  bagging_freq: 5

# Ensemble Configuration
ensemble:
  voting: "soft"
  weights: [1, 1, 1]  # weights for RF, XGB, LGB

# Training Configuration
training:
  test_size: 0.2
  random_state: 42
  n_jobs: -1
  verbose: 1
  early_stopping_rounds: 10
```

## Configuration Options Explained

### 1. Feature Extraction Options

#### TLS Features
- `max_handshake_size`: Maximum size of TLS handshake to analyze
- `include_extensions`: Whether to include TLS extensions in analysis
- `certificate_analysis`: Enable detailed certificate analysis

#### Statistical Features
- `block_size`: Size of blocks for statistical analysis
- `use_entropy`: Enable entropy calculation
- `byte_frequency`: Enable byte frequency analysis

#### Behavioral Features
- `sequence_length`: Length of sequence for pattern analysis
- `api_call_tracking`: Enable API call tracking
- `system_call_tracking`: Enable system call tracking

#### Flow Features
- `max_packets`: Maximum number of packets to analyze
- `include_timing`: Include packet timing information
- `direction_analysis`: Analyze packet flow directions

### 2. Model Options

#### Random Forest
- `n_estimators`: Number of trees
- `max_depth`: Maximum depth of trees
- `min_samples_split`: Minimum samples required to split
- `class_weight`: Handle class imbalance

#### XGBoost
- `max_depth`: Maximum tree depth
- `learning_rate`: Boosting learning rate
- `subsample`: Subsample ratio of training instances
- `colsample_bytree`: Subsample ratio of columns

#### LightGBM
- `num_leaves`: Maximum number of leaves
- `min_data_in_leaf`: Minimum data in leaves
- `feature_fraction`: Feature subsampling ratio
- `bagging_freq`: Bagging frequency

## Usage Examples

### 1. Modifying Feature Extraction
```yaml
# Enable additional TLS features
feature_extraction:
  tls:
    enabled: true
    max_handshake_size: 2048
    include_extensions: true
    certificate_analysis: true
```

### 2. Tuning Model Parameters
```yaml
# Adjust Random Forest parameters
random_forest:
  n_estimators: 200
  max_depth: 10
  min_samples_split: 5
  class_weight: "balanced"
```

### 3. Ensemble Configuration
```yaml
# Modify ensemble weights
ensemble:
  voting: "soft"
  weights: [2, 1, 1]  # Give more weight to Random Forest
```

## Best Practices

1. **Feature Selection**
   - Enable only necessary features
   - Adjust parameters based on available resources
   - Monitor feature extraction time

2. **Model Tuning**
   - Start with default parameters
   - Use cross-validation for parameter tuning
   - Monitor training time and memory usage

3. **Performance Optimization**
   - Adjust n_jobs for parallel processing
   - Enable GPU acceleration where available
   - Use early stopping for gradient boosting models