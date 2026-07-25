
# Model Card — Quantum Malware Hunter (Template)

**Model ID:** TBD  
**Schema Version:** v0  
**Schema Hash:** (see configs/schema_hash.txt)  
**Dataset(s):** CIC-IDS2017 flows subset; NSL-KDD (optional); EMBER subset (optional)  
**Task:** Binary classification (benign vs malicious) or multi-class

## 1. Training Summary
- Features: see `configs/schema.json`
- Split: 70/15/15 stratified (suggested)
- Seeds: 42 (Python), model-specific seeds recorded
- Hardware/OS: Windows 11 (x64), Arch Linux (x64)

## 2. Metrics
- Accuracy: 
- Precision:
- Recall:
- F1:
- PR-AUC:

## 3. Risks & Limitations
- Class imbalance, dataset bias, simulated vs real traffic gaps
- Quantum simulator scalability limits

## 4. Security
- Dependency pins, SBOM plan, checksums of model artifacts
- No real malware samples in repository
