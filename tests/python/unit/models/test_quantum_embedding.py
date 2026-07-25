# Tests quantum embedding behavior.
"""
Tests for quantum feature mapping and embedding functionality.
Tests both the QuantumFeatureMap class and quantum_embed function.
"""
import numpy as np, pytest

pytest.importorskip("pennylane")

from service.feature_map import QuantumFeatureMap
from models.train_qkernel import quantum_embed

@pytest.fixture
def sample_data():
    """Generate sample data for testing."""
    rng = np.random.RandomState(42)
    X = rng.rand(10, 4)  # 10 samples, 4 features
    X = (X - 0.5) * 2  # Scale to [-1, 1] for more robust testing
    return X

def test_quantum_feature_map_basics(sample_data):
    """Test basic functionality of QuantumFeatureMap."""
    qmap = QuantumFeatureMap(n_wires=6, shots=None, seed=42)
    x = sample_data[0]  # Single sample
    
    # Test single vector transformation
    result = qmap._circuit(x)
    assert len(result) == 6, "Output dimension should match n_wires"
    assert all(-1 <= val <= 1 for val in result), "Quantum expectation values must be in [-1,1]"
    
    # Test reproducibility
    result2 = qmap._circuit(x)
    np.testing.assert_array_almost_equal(result, result2, 
                                       err_msg="Same input should give same output")

def test_quantum_embedding_batched(sample_data):
    """Test quantum_embed function with batched input."""
    # Test with different batch sizes
    X_q1 = quantum_embed(sample_data, n_wires=6, shots=None)
    X_q2 = quantum_embed(sample_data[:5], n_wires=6, shots=None)  # Test smaller batch
    
    assert X_q1.shape == (10, 6), "Wrong output shape for full batch"
    assert X_q2.shape == (5, 6), "Wrong output shape for partial batch"
    assert np.all(np.abs(X_q1) <= 1.0), "Values must be in [-1,1]"
    
    # Check if first 5 samples match in both runs
    np.testing.assert_array_almost_equal(X_q1[:5], X_q2,
                                       err_msg="Batch size shouldn't affect results")

def test_quantum_feature_map_shots():
    """Test QuantumFeatureMap with different shot counts."""
    x = np.array([0.1, -0.2, 0.3, -0.4])
    
    # Compare results with and without shots
    qmap_exact = QuantumFeatureMap(n_wires=4, shots=None, seed=42)
    qmap_shots = QuantumFeatureMap(n_wires=4, shots=1000, seed=42)
    
    result_exact = qmap_exact._circuit(x)
    result_shots = qmap_shots._circuit(x)
    
    # With shots, results should be close but not exactly equal
    assert np.allclose(result_exact, result_shots, atol=0.1), \
        "Shot-based results should approximate exact results"
    assert not np.array_equal(result_exact, result_shots), \
        "Shot-based results shouldn't be exactly equal to exact results"

def test_quantum_feature_map_edge_cases():
    """Test edge cases and error handling."""
    qmap = QuantumFeatureMap(n_wires=4, shots=None)
    
    # Test zero vector
    x_zero = np.zeros(4)
    result_zero = qmap._circuit(x_zero)
    assert len(result_zero) == 4, "Should handle zero vector"
    
    # Test extreme values
    x_extreme = np.array([1.0, -1.0, 1.0, -1.0])
    result_extreme = qmap._circuit(x_extreme)
    assert np.all(np.abs(result_extreme) <= 1.0), "Should handle extreme values"
    
    # Test different input sizes
    x_short = np.array([0.1, 0.2])  # Shorter than n_wires
    result_short = qmap._circuit(x_short)
    assert len(result_short) == 4, "Should handle shorter input"
    
    x_long = np.array([0.1] * 6)  # Longer than n_wires
    result_long = qmap._circuit(x_long)
    assert len(result_long) == 4, "Should handle longer input"

def test_quantum_embed_reproducibility(sample_data):
    """Test reproducibility of quantum embedding."""
    # Multiple runs should give same results with same seed
    results = []
    for _ in range(3):
        X_q = quantum_embed(sample_data, n_wires=6, shots=None)
        results.append(X_q)
    
    for i in range(len(results) - 1):
        np.testing.assert_array_almost_equal(
            results[i], results[i + 1],
            err_msg=f"Run {i} and {i + 1} gave different results"
        )

def test_quantum_embedding_invariants(sample_data):
    """Test mathematical properties and invariants."""
    X_q = quantum_embed(sample_data, n_wires=6, shots=None)
    
    # Test normalization bounds
    assert np.all(np.abs(X_q) <= 1.0), "Quantum values must be bounded"
    
    # Test if transformation preserves relative distances (approximately)
    from scipy.spatial.distance import pdist
    orig_dist = pdist(sample_data)
    quantum_dist = pdist(X_q)
    correlation = np.corrcoef(orig_dist, quantum_dist)[0,1]
    assert correlation > 0.1, "Should preserve some distance relationships"
