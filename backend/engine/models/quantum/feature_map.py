# Quantum feature map: encodes classical features into a PennyLane circuit
# (ZZ/PQC/hardware-efficient) for file_qsvc's quantum embedding stage.
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
        self.n_layers: int = (
            n_layers if n_layers is not None else max(1, int(np.clip(self.n_wires // 2, 1, 6)))
        )
        self.nonlinear = nonlinear
        self.entangler = entangler
        self.shots = shots
        self.seed = int(seed)

        try:
            self.dev = qml.device("default.qubit", wires=self.n_wires, shots=shots, seed=seed)
        except Exception:
            logger.exception("Failed to initialize PennyLane device")
            raise

        self._nonlin_fn: Callable[[np.ndarray], np.ndarray]
        if nonlinear == "sin":
            self._nonlin_fn = lambda x: np.sin(np.pi * x)
        elif nonlinear == "tanh":
            self._nonlin_fn = lambda x: np.tanh(x)
        else:
            self._nonlin_fn = lambda x: x + x ** 2

        if arch_type == "zz":
            self._qnode = qml.QNode(self._zz_circuit, self.dev)
        elif arch_type == "pqc":
            self._qnode = qml.QNode(self._pqc_circuit, self.dev)
        else:
            self._qnode = qml.QNode(self._efficient_circuit, self.dev)

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

    def _prepare_input(self, x: np.ndarray) -> np.ndarray:
        if x.size == 0:
            raise ValueError("Input vector cannot be empty")
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
