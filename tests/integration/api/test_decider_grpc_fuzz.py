# Fuzzes UploadAndDecide with random payloads split into random chunk sizes.
import contextlib, importlib

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

grpc = pytest.importorskip("grpc")
try:
    stubs = importlib.import_module("backend.api.gRPC.stubs")
except ImportError as exc:
    pytest.skip(str(exc), allow_module_level=True)

from backend.api.gRPC.clients.common import auth_metadata
from backend.api.gRPC.decider_server import create_server

pb2 = stubs.pb2
pbg = stubs.pbg


@contextlib.asynccontextmanager
async def running_server():
    server, port = create_server("127.0.0.1", 0)
    await server.start()
    try:
        yield f"127.0.0.1:{port}"
    finally:
        await server.stop(0)


@given(
    payload=st.binary(min_size=1, max_size=4096),
    chunk_sizes=st.lists(st.integers(min_value=1, max_value=512), min_size=1, max_size=20),
)
@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@pytest.mark.anyio
async def test_upload_and_decide_never_crashes_on_valid_chunk_streams(payload, chunk_sizes):
    async with running_server() as target:
        async def chunks():
            offset = 0
            first = True
            while offset < len(payload):
                size = chunk_sizes[0] if chunk_sizes else len(payload) - offset
                piece = payload[offset:offset + max(size, 1)]
                offset += len(piece)
                yield pb2.FileChunk(
                    data=piece,
                    path="fuzz.bin" if first else "",
                    offset=offset - len(piece),
                    eof=offset >= len(payload),
                )
                first = False

        async with grpc.aio.insecure_channel(target) as channel:
            stub = pbg.DeciderStub(channel)
            response = await stub.UploadAndDecide(chunks(), metadata=auth_metadata())

    assert response.decision.verdict in {"malicious", "benign", "unknown"}
    assert 0.0 <= response.decision.score <= 1.0
    assert 0.0 <= response.decision.confidence <= 1.0
