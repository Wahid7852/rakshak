# Initializes the service package.
"""
RAKSHAK Service Module

This module provides the core service components for RAKSHAK quantum ML security system.
Includes feature maps, model registry, and prediction components.
"""
from __future__ import annotations

from .feature_map import QuantumFeatureMap
from .model_registry import (
    ModelInfo,
    get_current_model_info,
    set_current_model_id
)
from .predict_qml import load_bundle

# predict_qkernel needs qiskit_machine_learning, an optional/heavy extra -
# import lazily so the rest of this package works without it installed.
try:
    from .predict_qkernel import PredictorQKernel
except ImportError:
    PredictorQKernel = None

__all__ = [
    'QuantumFeatureMap',
    'ModelInfo',
    'get_current_model_info',
    'set_current_model_id',
    'PredictorQKernel',
    'load_bundle'
]