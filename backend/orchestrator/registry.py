# Coordinates backend orchestration for registry.
from __future__ import annotations
import logging, math
from typing import Awaitable, Dict, Protocol

from .types import Decision

logger = logging.getLogger(__name__)


def _try_import(module_path: str, attr: str):
    try:
        module = __import__(module_path, fromlist=[attr])
        return module
    except Exception:
        logger.warning("registry: falling back to neutral stub, import failed for %s", module_path, exc_info=True)
        return None


# Your existing models (optional; fallbacks provided if missing)
# Logs
NGRAM = _try_import("backend.engine.models.classical.ngram", "ngram")
HST = _try_import("backend.engine.models.classical.hst", "hst")
SGD = _try_import("backend.engine.models.classical.sgd", "sgd")

# Files
FST = _try_import("backend.engine.features.file_static_triage", "file_static_triage")
FILE_RF = _try_import("backend.engine.models.classical.file_rf", "file_rf")
QSV = _try_import("backend.engine.models.quantum.qsvc", "qsvc")


class Detector(Protocol):
    name: str
    cost_ms_estimate: int

    def score(self, payload, context) -> Awaitable[Decision]:
        ...


def _neutral(name: str):
    async def _score(self, payload, context):
        return Decision(0.5, 0.0, "unknown", name)

    return type("Neutral", (object,), {"name": name, "cost_ms_estimate": 1, "score": _score})()


def get_registry() -> Dict[str, Detector]:
    reg: Dict[str, Detector] = {}

    # -------- Logs --------
    if NGRAM and hasattr(NGRAM, "Detector"):
        reg["log_ngram"] = NGRAM.Detector()
    else:
        class _MiniNGram:
            name, cost_ms_estimate = "log_ngram", 0

            def __init__(self):
                self.mu, self.n = 0.0, 0

            async def score(self, payload, ctx):
                L = float(len(str(payload)))
                self.n += 1
                self.mu = 0.99 * self.mu + 0.01 * L
                score = 1 / (1 + math.exp(-(L - self.mu) / 32.0))
                return Decision(score, min(1.0, self.n / 8.0), "malicious" if score >= 0.5 else "benign", self.name)

        reg["log_ngram"] = _MiniNGram()

    reg["log_hst"] = HST.Detector() if HST and hasattr(HST, "Detector") else _neutral("log_hst")
    reg["log_sgd"] = SGD.Detector() if SGD and hasattr(SGD, "Detector") else _neutral("log_sgd")

    # -------- Files --------
    reg["file_static"] = FST.Detector() if FST and hasattr(FST, "Detector") else _neutral("file_static")
    reg["file_ml_or_rf"] = FILE_RF.Detector() if FILE_RF and hasattr(FILE_RF, "Detector") else _neutral("file_ml_or_rf")

    # Sandbox signal, fed by backend/engine/sandbox's read-only bwrap analysis
    # (see backend/engine/sandbox/runner.py::sandbox_context for the ctx keys).
    class _SandboxSignal:
        name, cost_ms_estimate = "file_sandbox_signal", 3

        _EXECUTABLE_FORMATS = {"pe", "elf"}
        _BENIGN_EXTENSIONS = {
            ".txt", ".csv", ".json", ".png", ".jpg", ".jpeg", ".gif", ".pdf",
            ".doc", ".docx", ".xls", ".xlsx", ".mp3", ".mp4", ".log",
        }

        async def score(self, payload, ctx):
            b = float(ctx.get("sandbox_bytes", 0) or 0)
            if b <= 0 or ctx.get("sandbox_error"):
                return Decision(0.5, 0.0, "unknown", self.name)

            entropy = float(ctx.get("sandbox_entropy", 0) or 0)
            fmt = ctx.get("sandbox_format", "unknown")
            suspicious = ctx.get("sandbox_suspicious_strings", "[]")
            has_suspicious_strings = suspicious not in ("[]", "", None)
            timed_out = str(ctx.get("sandbox_timed_out", "")).lower() == "true"

            path = str(ctx.get("path", "")).lower()
            ext = path[path.rfind("."):] if "." in path else ""
            format_mismatch = fmt in self._EXECUTABLE_FORMATS and ext in self._BENIGN_EXTENSIONS

            s = 0.5
            if fmt in self._EXECUTABLE_FORMATS:
                s += 0.05
            if entropy > 7.5:
                s += 0.15
            if has_suspicious_strings:
                s += 0.1
            if format_mismatch:
                s += 0.2
            if timed_out:
                s += 0.05  # sample stalled the analyzer, mildly suspicious on its own

            score = min(1.0, s)
            conf = 0.35 if (has_suspicious_strings or format_mismatch or entropy > 7.5) else 0.15
            return Decision(score, conf, "malicious" if score >= 0.5 else "benign", self.name)

    reg["file_sandbox_signal"] = _SandboxSignal()

    # Dynamic (execution-based) signal, fed by DynamicSandboxAdapter when
    # RAKSHAK_SANDBOX_ADAPTER=dynamic (see dynamic_runner.py::dynamic_context
    # for the ctx keys). Off by default, so ctx usually won't have these keys
    # at all - that's the same "no signal" case as file_sandbox_signal sees
    # when sandbox_bytes is missing, and scores identically: unknown, conf 0.
    class _DynamicSignal:
        name, cost_ms_estimate = "file_dynamic_signal", 3

        @staticmethod
        def _is_nonempty_list_repr(raw) -> bool:
            return raw not in (None, "", "[]")

        async def score(self, payload, ctx):
            if ctx.get("dynamic_executed") != "True":
                return Decision(0.5, 0.0, "unknown", self.name)

            connected = self._is_nonempty_list_repr(ctx.get("dynamic_connect_attempts"))
            opened_outside = self._is_nonempty_list_repr(ctx.get("dynamic_opens_outside_sandbox"))
            timed_out = str(ctx.get("dynamic_timed_out", "")).lower() == "true"
            # child_execs always includes the sample itself - a comma in the
            # list repr means it's more than a single element, i.e. it spawned
            # at least one additional process
            child_execs = str(ctx.get("dynamic_child_execs", "[]"))
            spawned_children = "," in child_execs

            s = 0.5
            if connected:
                s += 0.15  # tried to reach the network, even though it's namespace-blocked
            if opened_outside:
                s += 0.25  # read outside its own sandbox - recon/credential-harvesting behavior
            if spawned_children:
                s += 0.1
            if timed_out:
                s += 0.05

            score = min(1.0, s)
            conf = 0.4 if (connected or opened_outside) else 0.15
            return Decision(score, conf, "malicious" if score >= 0.5 else "benign", self.name)

    reg["file_dynamic_signal"] = _DynamicSignal()

    # Quantum few-shot fallback (optional, auto-disabled if not present)
    reg["file_qsvc"] = QSV.Detector() if QSV and hasattr(QSV, "Detector") else _neutral("file_qsvc")

    return reg
