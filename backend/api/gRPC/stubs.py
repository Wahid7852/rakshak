# Loads generated decider protobuf modules.
import importlib, sys
from pathlib import Path


PACKAGED_PROTO_PY = Path(__file__).resolve().parent / "generated"
BUILD_PROTO_PY = Path(__file__).resolve().parents[3] / "build" / "proto" / "py"


def _load(module_name: str):
    last_error = None
    for proto_dir in (PACKAGED_PROTO_PY, BUILD_PROTO_PY):
        if not (proto_dir / f"{module_name}.py").is_file():
            continue
        proto_path = str(proto_dir)
        if proto_path not in sys.path:
            sys.path.insert(0, proto_path)
        try:
            return importlib.import_module(module_name)
        except ImportError as exc:
            last_error = exc

    raise ImportError(
        "Generated decider gRPC stubs are missing. "
        "Run `python scripts/dev/gen_decider_proto.py` first."
    ) from last_error


pb2 = _load("decision_pb2")
pbg = _load("decision_pb2_grpc")

__all__ = ["pb2", "pbg"]
