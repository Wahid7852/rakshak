# Tests the gRPC CLI clients' request-building logic (no real channel/server).
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

grpc = pytest.importorskip("grpc")

from backend.api.gRPC.clients.stream_logs import generator
from backend.api.gRPC.clients.upload_and_decide import gen_chunks


@pytest.mark.anyio
async def test_stream_logs_generator_wraps_each_line():
    lines = ["first line", "second line"]
    messages = [msg async for msg in generator(lines)]

    assert [m.text for m in messages] == lines
    assert len({m.id for m in messages}) == 2  # each line gets its own correlation id


@pytest.mark.anyio
async def test_gen_chunks_single_read_sets_path_and_eof(tmp_path):
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"small payload")

    chunks = [c async for c in gen_chunks(str(sample), {"k": "v"})]

    # small enough to fit in one read, then an empty EOF-marker chunk
    assert len(chunks) == 2
    assert chunks[0].data == b"small payload"
    assert chunks[0].path == str(sample)
    assert chunks[0].offset == 0
    assert chunks[0].eof is False
    assert dict(chunks[0].context) == {"k": "v"}

    assert chunks[1].data == b""
    assert chunks[1].path == ""
    assert chunks[1].offset == len(b"small payload")
    assert chunks[1].eof is True


@pytest.mark.anyio
async def test_gen_chunks_only_first_chunk_carries_path_and_context(tmp_path):
    sample = tmp_path / "big.bin"
    sample.write_bytes(b"x" * 300_000)  # bigger than the client's 128KiB read chunk

    chunks = [c async for c in gen_chunks(str(sample), {"k": "v"})]

    assert len(chunks) > 1
    assert chunks[0].path == str(sample)
    assert dict(chunks[0].context) == {"k": "v"}
    for c in chunks[1:]:
        assert c.path == ""
        assert dict(c.context) == {}
    assert chunks[-1].eof is True
    assert sum(len(c.data) for c in chunks) == 300_000


@pytest.mark.anyio
async def test_cli_decide_builds_log_event():
    from backend.api.gRPC.clients import cli_decide

    captured = {}

    class FakeStub:
        def __init__(self, channel):
            pass

        async def Decide(self, request, metadata=None):
            captured["request"] = request
            return MagicMock(decision="fake-decision")

    with patch("backend.api.gRPC.clients.cli_decide.pbg.DeciderStub", FakeStub), \
         patch("backend.api.gRPC.clients.cli_decide.aio.insecure_channel") as fake_channel, \
         patch("sys.argv", ["cli_decide", "--kind", "log", "--text", "auth fail"]):
        fake_channel.return_value.__aenter__ = AsyncMock(return_value=None)
        fake_channel.return_value.__aexit__ = AsyncMock(return_value=False)
        await cli_decide.main()

    event = captured["request"].event
    assert event.kind == 0
    assert event.text == "auth fail"


@pytest.mark.anyio
async def test_cli_decide_builds_file_event(tmp_path):
    from backend.api.gRPC.clients import cli_decide

    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"MZpayload")

    captured = {}

    class FakeStub:
        def __init__(self, channel):
            pass

        async def Decide(self, request, metadata=None):
            captured["request"] = request
            return MagicMock(decision="fake-decision")

    with patch("backend.api.gRPC.clients.cli_decide.pbg.DeciderStub", FakeStub), \
         patch("backend.api.gRPC.clients.cli_decide.aio.insecure_channel") as fake_channel, \
         patch("sys.argv", ["cli_decide", "--kind", "file", "--file", str(sample)]):
        fake_channel.return_value.__aenter__ = AsyncMock(return_value=None)
        fake_channel.return_value.__aexit__ = AsyncMock(return_value=False)
        await cli_decide.main()

    event = captured["request"].event
    assert event.kind == 1
    assert bytes(event.bytes) == b"MZpayload"
    assert event.path == str(sample)
