# Provides RAKSHAK support for conftest.
"""Unit test configuration and fixtures."""
import pytest, numpy as np
from pathlib import Path

@pytest.fixture
def test_data_dir():
    """Return path to test data directory."""
    return Path(__file__).parent.parent.parent / "data" / "test"

@pytest.fixture
def random_features():
    """Generate random feature vectors for testing."""
    def _generate(n_samples=100, n_features=10):
        return np.random.rand(n_samples, n_features).astype(np.float32)
    return _generate

@pytest.fixture
def random_labels():
    """Generate random binary labels for testing."""
    def _generate(n_samples=100):
        return np.random.randint(0, 2, n_samples)
    return _generate