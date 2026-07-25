# flake8: noqa E501
from __future__ import annotations
import json, os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple

import yaml

REGISTRY_PATH = Path("configs/model_registry.yaml")

@dataclass
class ModelInfo:
    model_id: str
    model_path: Path
    preproc_path: Path

def _load_yaml(p: Path) -> dict:
    if not p.exists():
        raise FileNotFoundError(f"Model registry not found: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}

def _newest_artifact(artifacts_dir: Path) -> Optional[Tuple[str, Path]]:
    """
    Find newest *_baseline_*.joblib (or any .joblib) in the artifacts dir.
    """
    if not artifacts_dir.exists():
        return None
    cands = sorted(artifacts_dir.glob("*.joblib"), key=lambda x: x.stat().st_mtime, reverse=True)
    for f in cands:
        # pick a model file, not a _preproc.joblib
        if not f.name.endswith("_preproc.joblib"):
            # model_id = filename without extension
            return (f.stem, f)
    return None

def get_current_model_info() -> ModelInfo:
    cfg = _load_yaml(REGISTRY_PATH)
    artifacts_dir = Path(cfg.get("artifacts_dir", "models/artifacts"))
    suffix = cfg.get("preproc_suffix", "_preproc.joblib")
    model_id = cfg.get("current_model_id") or ""

    if not model_id:
        auto = _newest_artifact(artifacts_dir)
        if not auto:
            raise RuntimeError("No model artifacts found. Train a baseline and try again.")
        model_id, model_path = auto
        preproc_path = artifacts_dir / f"{model_id}{suffix}"
        return ModelInfo(model_id=model_id, model_path=model_path, preproc_path=preproc_path)

    model_path = artifacts_dir / f"{model_id}.joblib"
    preproc_path = artifacts_dir / f"{model_id}{suffix}"
    if not model_path.exists():
        raise FileNotFoundError(f"Model file missing: {model_path}")
    if not preproc_path.exists():
        raise FileNotFoundError(f"Preprocessor file missing: {preproc_path}")
    return ModelInfo(model_id=model_id, model_path=model_path, preproc_path=preproc_path)

def set_current_model_id(model_id: str) -> None:
    cfg = _load_yaml(REGISTRY_PATH)
    cfg["current_model_id"] = model_id
    REGISTRY_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
