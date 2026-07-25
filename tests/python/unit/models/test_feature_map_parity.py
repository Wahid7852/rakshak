# Tests that the vendored production feature map hasn't drifted from the
# legacy research copy it was vendored from.
import numpy as np, pytest

pytest.importorskip("pennylane")

from service.feature_map import QuantumFeatureMap as ServiceFeatureMap
from backend.engine.models.quantum.feature_map import QuantumFeatureMap as BackendFeatureMap


@pytest.mark.parametrize("arch_type", ["zz", "pqc", "efficient"])
@pytest.mark.parametrize("nonlinear", ["sin", "tanh", "poly"])
def test_vendored_feature_map_matches_service_copy(arch_type, nonlinear):
    """backend/engine/models/quantum/feature_map.py is a hand-copied vendor of
    service/feature_map.py (kept separate so production doesn't have to pull in
    qiskit_machine_learning just for this class - see that file's header comment).
    Nothing enforces the two stay in sync, so if a future fix lands in one and
    not the other, this is what catches the silent drift."""
    x = np.array([0.1, -0.4, 0.9, -0.9, 0.0, 0.5])

    service_map = ServiceFeatureMap(n_wires=6, arch_type=arch_type, nonlinear=nonlinear, seed=7)
    backend_map = BackendFeatureMap(n_wires=6, arch_type=arch_type, nonlinear=nonlinear, seed=7)

    assert backend_map.n_layers == service_map.n_layers
    np.testing.assert_allclose(backend_map(x), service_map(x), rtol=1e-6, atol=1e-6)
