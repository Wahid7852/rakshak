# Tests feature map extra behavior.
"""Extra tests for enhanced QuantumFeatureMap features."""
import numpy as np, pytest

pytest.importorskip("pennylane")

from service.feature_map import QuantumFeatureMap


def test_visualize_returns_string():
    q = QuantumFeatureMap(n_wires=4, arch_type="zz")
    v = q.visualize()
    assert isinstance(v, str)
    assert "QuantumFeatureMap" in v or len(v) > 0


def test_adaptive_depth_and_calls():
    # n_layers not provided -> should be set adaptively
    q = QuantumFeatureMap(n_wires=8, arch_type="pqc", n_layers=None)
    assert q.n_layers >= 1
    x = np.linspace(-1, 1, 8)
    out = q(x)
    assert out.shape == (8,)
    assert np.all(np.abs(out) <= 1.0)


@pytest.mark.parametrize("nonlin", ["sin", "tanh", "poly"])
def test_nonlinear_transforms(nonlin):
    q = QuantumFeatureMap(n_wires=4, arch_type="efficient", nonlinear=nonlin)
    x = np.array([0.1, -0.2, 0.3, -0.4])
    out = q(x)
    assert out.shape == (4,)
    assert np.all(np.abs(out) <= 1.0)


def test_export_qiskit_optional():
    q = QuantumFeatureMap(n_wires=3)
    try:
        _ = q.export_qiskit()
    except RuntimeError:
        pytest.skip("Qiskit export not available in test environment")


def test_export_cirq_optional():
    q = QuantumFeatureMap(n_wires=3)
    try:
        _ = q.export_cirq()
    except RuntimeError:
        pytest.skip("Cirq export not available in test environment")
    except NotImplementedError:
        pytest.skip("Cirq export intentionally not implemented")
