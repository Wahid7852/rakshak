# Provides a gRPC client for stream logs workflows.

import asyncio, argparse, os, uuid, grpc
from grpc import aio
from backend.api.gRPC.clients.common import auth_metadata
from backend.api.gRPC.stubs import pb2, pbg


async def generator(lines):
    for ln in lines:
        yield pb2.LogLine(id=str(uuid.uuid4()), text=ln, context={})


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=50055)
    ap.add_argument("--file", help="text file with one log line per row")
    args = ap.parse_args()

    lines = ["test log line"] if not args.file else open(args.file, "r", encoding="utf-8").read().splitlines()

    use_tls = os.getenv("RAKSHAK_TLS", "0") == "1"
    if use_tls:
        with open("client.crt", "rb") as f:
            creds = grpc.ssl_channel_credentials(f.read())
        ch = aio.secure_channel(f"{args.host}:{args.port}", creds)
    else:
        ch = aio.insecure_channel(f"{args.host}:{args.port}")

    async with ch:
        stub = pbg.DeciderStub(ch)
        call = stub.StreamLogs(generator(lines), metadata=auth_metadata())
        async for d in call:
            print(d.id, d.decision)


if __name__ == "__main__":
    asyncio.run(main())
