# Data Pipeline Documentation

> **Status: not what's live.** Describes the same disconnected
> encrypted-file/TLS pipeline as `docs/overview.md` - `src/encryption/`
> doesn't exist in the current tree, and the data files this pipeline reads
> (`features.csv`, `labels.csv`) aren't present. See root `README.md` for
> the actual live system.

## Overview
The data pipeline consists of three main stages: encryption, feature extraction, and preprocessing. This document details each stage's implementation and workflow.

## 1. Encryption Stage
### Process
```bash
python src/encryption/encrypt_files.py --indir Dataset/train --outdir Dataset/encrypted_train
```

- **Input**: Raw files from Dataset/train/ and Dataset/test/
- **Output**: Encrypted files in Dataset/encrypted_train/ and Dataset/encrypted_test/
- **Method**: AES-128-CBC with per-file keys

### Implementation Details
- Each file is encrypted individually
- Unique key and IV generation per file
- Encryption metadata stored with file

## 2. Feature Extraction Stage
### Process
```bash
python features.py --indir Dataset/encrypted_train --outcsv features.csv
```

- **Input**: Encrypted files
- **Output**: CSV file containing extracted features
- **Features Categories**:
  - TLS handshake information
  - File metadata
  - Statistical measures
  - Behavioral indicators

### Key Features Extracted
1. TLS-based features
2. Statistical patterns
3. Behavioral indicators
4. Flow-based metrics

## 3. Preprocessing Stage
### Process
Handled in `src/models/train_models.py`

### Steps
1. **Data Loading**
   - Load features and labels
   - Match samples using base filenames

2. **Data Cleaning**
   - Remove constant columns
   - Remove zero-valued columns
   - Handle NaN values
   - Remove highly correlated features

3. **Data Transformation**
   - Feature scaling
   - Train/test split
   - Label encoding

### Data Quality Checks
- Correlation analysis (threshold: 0.95)
- Missing value detection
- Constant feature detection
- Feature distribution analysis

## Data Flow Diagram
```
Raw Files
   ↓
Encryption (AES-128-CBC)
   ↓
Encrypted Files
   ↓
Feature Extraction
   ↓
Raw Features (CSV)
   ↓
Preprocessing
   ↓
Clean Features
   ↓
Model Training
```

## Directory Structure
```
Dataset/
├── train/
├── test/
├── encrypted_train/
└── encrypted_test/

data/
├── raw/
├── processed/
└── features/
```

## Quality Control
- Validation checks at each stage
- Error logging and handling
- Data integrity verification
- Feature quality assessment