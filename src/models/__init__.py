# Initializes the src.models package.
"""TLS-based malware detection model implementations."""

from .rf import RandomForestModel
from .base import BaseModel

__all__ = ['RandomForestModel', 'BaseModel']