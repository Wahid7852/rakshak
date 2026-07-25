# Provides legacy service support for feature map.
from __future__ import annotations
import logging
from typing import List, Optional, Literal, Callable
import numpy as np, pennylane as qml
logger = logging.getLogger(__name__)


class QuantumFeatureMap:
    """Enhanced quantum feature map with multiple architecture options.

    This class exposes:
    - choice of architecture: 'zz' (ZZFeatureMap-like), 'pqc' (PQC-style), 'efficient' (hardware efficient)
    - configurable nonlinear transform: 'sin', 'tanh', 'poly'
    - adaptive layer depth heuristic based on input dimensionality
    - visualization helper using pennylane.draw
    - export helpers for qiskit/cirq (best-effort, optional)
    """

    def __init__(
        self,
        n_wires: int = 6,
        arch_type: Literal["zz", "pqc", "efficient"] = "zz",
        n_layers: Optional[int] = None,
        nonlinear: Literal["sin", "tanh", "poly"] = "sin",
        entangler: Literal["cx", "cz", "all"] = "cx",
        shots: Optional[int] = None,
        seed: int = 42,
    ) -> None:
        self.n_wires = int(n_wires)
        self.arch_type = arch_type
        self.n_layers = n_layers
        self.nonlinear = nonlinear
        self.entangler = entangler
        self.shots = shots
        self.seed = int(seed)

        # Lazy device initialization
        try:
            self.dev = qml.device("default.qubit", wires=self.n_wires, shots=shots, seed=seed)
        except Exception as e:  # pragma: no cover - environment dependent
            logger.exception("Failed to initialize PennyLane device")
            raise

        # Adaptive depth if not provided
        if self.n_layers is None:
            self.n_layers = max(1, int(np.clip(self.n_wires // 2, 1, 6)))

        # Map nonlinear transform
        self._nonlin_fn: Callable[[np.ndarray], np.ndarray]
        if nonlinear == "sin":
            self._nonlin_fn = lambda x: np.sin(np.pi * x)
        elif nonlinear == "tanh":
            self._nonlin_fn = lambda x: np.tanh(x)
        else:
            # polynomial transform: x -> x + x^2
            self._nonlin_fn = lambda x: x + x ** 2

        # Build QNode bound to selected circuit
        if arch_type == "zz":
            self._qnode = qml.QNode(self._zz_circuit, self.dev)
        elif arch_type == "pqc":
            self._qnode = qml.QNode(self._pqc_circuit, self.dev)
        else:
            self._qnode = qml.QNode(self._efficient_circuit, self.dev)

    # ----------------------------- circuits -----------------------------
    def _zz_circuit(self, x: np.ndarray) -> List[float]:
        x_pad = np.zeros(self.n_wires)
        L = min(len(x), self.n_wires)
        x_pad[:L] = x[:L]

        for layer in range(self.n_layers):
            for i in range(self.n_wires):
                qml.Hadamard(wires=i)
            for i in range(self.n_wires):
                qml.RZ(np.pi * x_pad[i], wires=i)
            for i in range(self.n_wires):
                for j in range(i + 1, self.n_wires):
                    qml.CNOT(wires=[i, j])
                    qml.RZ(np.pi * x_pad[i] * x_pad[j], wires=j)
                    qml.CNOT(wires=[i, j])
            if layer < self.n_layers - 1:
                for i in range(self.n_wires):
                    qml.RY(self._nonlin_fn(x_pad[i]), wires=i)

        return [qml.expval(qml.PauliZ(i)) for i in range(self.n_wires)]

    def _pqc_circuit(self, x: np.ndarray) -> List[float]:
        x_pad = np.zeros(self.n_wires)
        L = min(len(x), self.n_wires)
        x_pad[:L] = x[:L]

        # initial layer
        for i in range(self.n_wires):
            qml.Hadamard(wires=i)

        for layer in range(self.n_layers):
            for i in range(self.n_wires):
                qml.RX(x_pad[i], wires=i)
                qml.RY(self._nonlin_fn(x_pad[i]), wires=i)
                qml.RZ(np.pi * x_pad[i], wires=i)

            if self.entangler == "all":
                for i in range(self.n_wires):
                    for j in range(i + 1, self.n_wires):
                        qml.CRZ(x_pad[i] * x_pad[j], wires=[i, j])
            else:
                for i in range(self.n_wires - 1):
                    if self.entangler == "cx":
                        qml.CNOT(wires=[i, i + 1])
                    else:
                        qml.CZ(wires=[i, i + 1])

            if layer < self.n_layers - 1:
                for i in range(self.n_wires):
                    qml.RZ(np.sin(x_pad[i] * np.pi), wires=i)

        for i in range(self.n_wires):
            qml.RY(np.pi / 4, wires=i)
        return [qml.expval(qml.PauliZ(i)) for i in range(self.n_wires)]

    def _efficient_circuit(self, x: np.ndarray) -> List[float]:
        x_pad = np.zeros(self.n_wires)
        L = min(len(x), self.n_wires)
        x_pad[:L] = x[:L]

        for i in range(self.n_wires):
            qml.RY(np.pi / 4, wires=i)

        for layer in range(self.n_layers):
            for i in range(self.n_wires):
                qml.Rot(x_pad[i], x_pad[i] ** 2, np.pi * x_pad[i], wires=i)
            for i in range(self.n_wires):
                qml.CZ(wires=[i, (i + 1) % self.n_wires])
            if layer < self.n_layers - 1:
                for i in range(self.n_wires):
                    qml.RZ(np.tanh(x_pad[i]), wires=i)

        return [qml.expval(qml.PauliZ(i)) for i in range(self.n_wires)]

    # ----------------------------- helpers -----------------------------
    def _prepare_input(self, x: np.ndarray) -> np.ndarray:
        if x.size == 0:
            raise ValueError("Input vector cannot be empty")
        # normalize to [-1,1]
        x = np.asarray(x, dtype=float)
        xmin = np.min(x)
        xmax = np.max(x)
        if xmax - xmin < 1e-8:
            return np.zeros_like(x)
        x_norm = 2 * (x - xmin) / (xmax - xmin + 1e-12) - 1
        return x_norm

    def __call__(self, x: np.ndarray) -> np.ndarray:
        x_norm = self._prepare_input(np.asarray(x))
        return np.asarray(self._qnode(x_norm), dtype=np.float32)

    def _circuit(self, x: np.ndarray) -> np.ndarray:
        """Evaluated circuit output - alias for __call__ (the raw _zz_circuit
        etc methods return unevaluated ExpectationMP objects, not numbers)."""
        return self(x)

    # Public utility: draw/visualize the circuit
    def visualize(self) -> str:
        """Return a text diagram of the underlying circuit.

        Uses Pennylane drawer; falls back to string if drawer unavailable.
        """
        try:
            return qml.draw(self._qnode, expansion_strategy='device')(np.zeros(self.n_wires))
        except Exception:
            # Fallback: return a minimal description
            return f"QuantumFeatureMap(arch={self.arch_type}, wires={self.n_wires}, layers={self.n_layers})"

    # ----------------------------- optional interop -----------------------------
    def export_qiskit(self):
        """Best-effort OpenQASM export; raises RuntimeError if unavailable."""
        try:
            import pennylane as qml_
            return qml_.transforms.to_openqasm(self._qnode)(np.zeros(self.n_wires))
        except ImportError as e:
            raise RuntimeError(f"qiskit export unavailable: {e}") from e
        except Exception as e:
            raise RuntimeError(f"qiskit export failed: {e}") from e

    def export_cirq(self):
        """Cirq export is not implemented - no in-repo need for it yet."""
        raise NotImplementedError("export_cirq is not implemented")


def frame_payload(payload):
    """Convert an incoming payload dict into a pandas DataFrame row.

    This helper is intentionally small: it turns mapping-like payloads into
    a one-row DataFrame for downstream preprocessing in predictors.
    """
    try:
        import pandas as pd
    except Exception:
        raise RuntimeError("pandas is required for frame_payload but is not available")

    if payload is None:
        return pd.DataFrame()

    # If payload already looks like a DataFrame-like object, try to coerce
    if hasattr(payload, "to_dict") and not isinstance(payload, dict):
        try:
            return pd.DataFrame([payload.to_dict()])
        except Exception:
            pass

    if isinstance(payload, dict):
        return pd.DataFrame([payload])

    # Fallback: try to coerce sequence of pairs
    try:
        return pd.DataFrame([dict(payload)])
    except Exception:
        raise ValueError("Unsupported payload format for frame_payload")

