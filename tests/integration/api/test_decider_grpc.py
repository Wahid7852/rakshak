# Tests authenticated unary, streaming-log, and streamed-file gRPC behavior.
import contextlib, importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

grpc = pytest.importorskip("grpc")
try:
    stubs = importlib.import_module("backend.api.gRPC.stubs")
except ImportError as exc:
    pytest.skip(str(exc), allow_module_level=True)

from backend.api.gRPC.clients.common import auth_metadata
from backend.api.gRPC.decider_server import DeciderService, create_server
from backend.engine.adapters.sandbox import StaticSandboxAdapter
from backend.engine.quarantine import QuarantineManager
from backend.observability.metrics import REQUEST_COUNT
from backend.orchestrator.types import Decision

pb2 = stubs.pb2
pbg = stubs.pbg


@contextlib.asynccontextmanager
async def running_server(service=None):
    server, port = create_server("127.0.0.1", 0, service=service)
    await server.start()
    try:
        yield f"127.0.0.1:{port}"
    finally:
        await server.stop(0)


@pytest.fixture
async def grpc_target():
    async with running_server() as target:
        yield target


@pytest.mark.anyio
async def test_decide_requires_api_key(grpc_target):
    async with grpc.aio.insecure_channel(grpc_target) as channel:
        stub = pbg.DeciderStub(channel)
        with pytest.raises(grpc.aio.AioRpcError) as exc_info:
            await stub.Decide(pb2.DecideRequest(
                event=pb2.Event(kind=pb2.Event.LOG, text="auth fail 10.0.0.1")
            ))

    assert exc_info.value.code() == grpc.StatusCode.UNAUTHENTICATED


@pytest.mark.anyio
async def test_decide_log(grpc_target):
    async with grpc.aio.insecure_channel(grpc_target) as channel:
        stub = pbg.DeciderStub(channel)
        response = await stub.Decide(
            pb2.DecideRequest(event=pb2.Event(
                kind=pb2.Event.LOG,
                text="auth fail 10.0.0.1",
            )),
            metadata=auth_metadata(),
        )

    assert response.decision.verdict in {"malicious", "benign", "unknown"}
    assert 0.0 <= response.decision.score <= 1.0
    assert 0.0 <= response.decision.confidence <= 1.0


@pytest.mark.anyio
async def test_stream_logs_preserves_correlation_ids(grpc_target):
    async def messages():
        yield pb2.LogLine(id="log-1", text="normal service start")
        yield pb2.LogLine(id="log-2", text="authentication failure")

    async with grpc.aio.insecure_channel(grpc_target) as channel:
        stub = pbg.DeciderStub(channel)
        call = stub.StreamLogs(messages(), metadata=auth_metadata())
        responses = [response async for response in call]

    assert [response.id for response in responses] == ["log-1", "log-2"]
    assert all(response.decision.used for response in responses)


@pytest.mark.anyio
async def test_upload_and_decide_accepts_ordered_chunks(grpc_target):
    async def chunks():
        first = b"MZ" + (b"payload" * 8)
        yield pb2.FileChunk(data=first, path="sample.exe", offset=0)
        yield pb2.FileChunk(data=b"tail", offset=len(first), eof=True)

    async with grpc.aio.insecure_channel(grpc_target) as channel:
        stub = pbg.DeciderStub(channel)
        response = await stub.UploadAndDecide(chunks(), metadata=auth_metadata())

    assert response.decision.verdict in {"malicious", "benign", "unknown"}
    assert 0.0 <= response.decision.score <= 1.0


@pytest.mark.anyio
async def test_upload_rejects_invalid_offset(grpc_target):
    async def chunks():
        yield pb2.FileChunk(data=b"MZpayload", offset=4, eof=True)

    async with grpc.aio.insecure_channel(grpc_target) as channel:
        stub = pbg.DeciderStub(channel)
        with pytest.raises(grpc.aio.AioRpcError) as exc_info:
            await stub.UploadAndDecide(chunks(), metadata=auth_metadata())

    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "invalid chunk offset" in exc_info.value.details()


@pytest.mark.anyio
async def test_upload_rejects_missing_eof(grpc_target):
    async def chunks():
        yield pb2.FileChunk(data=b"MZpayload", offset=0)

    async with grpc.aio.insecure_channel(grpc_target) as channel:
        stub = pbg.DeciderStub(channel)
        with pytest.raises(grpc.aio.AioRpcError) as exc_info:
            await stub.UploadAndDecide(chunks(), metadata=auth_metadata())

    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    assert "missing EOF" in exc_info.value.details()


@pytest.mark.anyio
async def test_upload_enforces_configured_size_limit():
    service = DeciderService(max_file_bytes=4)

    async def chunks():
        yield pb2.FileChunk(data=b"12345", offset=0, eof=True)

    async with running_server(service) as target:
        async with grpc.aio.insecure_channel(target) as channel:
            stub = pbg.DeciderStub(channel)
            with pytest.raises(grpc.aio.AioRpcError) as exc_info:
                await stub.UploadAndDecide(chunks(), metadata=auth_metadata())

    assert exc_info.value.code() == grpc.StatusCode.RESOURCE_EXHAUSTED


def _service_with_forced_verdict(decision: Decision, tmp_path) -> DeciderService:
    fake_router = SimpleNamespace(decide=AsyncMock(return_value=decision))
    service = DeciderService(router=fake_router, sandbox_factory=StaticSandboxAdapter)
    service.quarantine = QuarantineManager(tmp_path / "quarantine")
    return service


@pytest.mark.anyio
async def test_upload_and_decide_quarantines_confident_malicious(tmp_path):
    service = _service_with_forced_verdict(Decision(0.95, 0.9, "malicious", "test"), tmp_path)

    async def chunks():
        yield pb2.FileChunk(data=b"evil content", path="evil.exe", offset=0, eof=True)

    async with running_server(service) as target:
        async with grpc.aio.insecure_channel(target) as channel:
            stub = pbg.DeciderStub(channel)
            response = await stub.UploadAndDecide(chunks(), metadata=auth_metadata())

    assert response.decision.verdict == "malicious"
    assert len(service.quarantine.list_quarantined()) == 1


@pytest.mark.anyio
async def test_upload_and_decide_does_not_quarantine_benign(tmp_path):
    service = _service_with_forced_verdict(Decision(0.1, 0.8, "benign", "test"), tmp_path)

    async def chunks():
        yield pb2.FileChunk(data=b"fine content", path="fine.txt", offset=0, eof=True)

    async with running_server(service) as target:
        async with grpc.aio.insecure_channel(target) as channel:
            stub = pbg.DeciderStub(channel)
            response = await stub.UploadAndDecide(chunks(), metadata=auth_metadata())

    assert response.decision.verdict == "benign"
    assert service.quarantine.list_quarantined() == []


@pytest.mark.anyio
async def test_decide_records_a_request_metric(grpc_target):
    metric = REQUEST_COUNT.labels(protocol="grpc", endpoint="Decide", status="ok")
    before = metric._value.get()

    async with grpc.aio.insecure_channel(grpc_target) as channel:
        stub = pbg.DeciderStub(channel)
        await stub.Decide(
            pb2.DecideRequest(event=pb2.Event(kind=pb2.Event.LOG, text="auth fail 10.0.0.1")),
            metadata=auth_metadata(),
        )

    assert metric._value.get() == before + 1
