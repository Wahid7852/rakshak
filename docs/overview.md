# Project Overview

> **Status: not what's live.** This describes an encrypted-file/TLS-traffic-analysis
> pipeline (`src/features/`, `src/models/`) that's real code but was never
> wired to real data (`data/processed/features.csv`/`labels.csv` don't exist)
> or to `backend/`. The actual running system is the log/file scanning
> cascade under `backend/orchestrator/` - see the root `README.md` and
> `docs/results.md` for what's really live and its real measured numbers.

## Objective
Develop a machine learning-based system for detecting malware in encrypted files using TLS traffic analysis, achieving 80-90% accuracy without payload inspection.

## Key Features
- Non-payload based detection using only metadata and TLS handshake information
- Support for multiple malware categories (ransomware, trojans, worms)
- Ensemble approach combining multiple machine learning models
- Robust feature extraction from encrypted traffic

## System Architecture
1. **Data Encryption Layer**
   - AES-128-CBC encryption
   - Per-file key and IV generation
   - Secure file handling

2. **Feature Extraction Layer**
   - TLS handshake analysis
   - Metadata extraction
   - Statistical feature computation

3. **Model Layer**
   - Random Forest Classifier
   - XGBoost
   - LightGBM
   - Ensemble voting classifier

4. **Evaluation Layer**
   - Performance metrics calculation
   - Visualization generation
   - Model comparison

## Technology Stack
- Python 3.13+
- scikit-learn for machine learning
- pycryptodome for encryption
- pandas and numpy for data processing
- matplotlib and seaborn for visualization