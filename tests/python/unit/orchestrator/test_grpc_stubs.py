# Tests generated gRPC stub loading.
import importlib, pytest


try:
    stubs = importlib.import_module("backend.api.gRPC.stubs")
except ImportError as exc:
    pytest.skip(str(exc), allow_module_level=True)


def test_decider_stubs_expose_expected_messages():
    assert hasattr(stubs.pb2, "DecideRequest")
    assert hasattr(stubs.pb2, "FileChunk")
    assert hasattr(stubs.pbg, "DeciderStub")
