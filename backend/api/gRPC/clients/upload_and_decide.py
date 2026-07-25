# Provides a gRPC client for upload and decide workflows.

import asyncio, argparse, os, grpc
from grpc import aio
from backend.api.gRPC.clients.common import auth_metadata
from backend.api.gRPC.stubs import pb2, pbg

CHUNK = 128 * 1024
async def gen_chunks(path, ctx):
    sent = 0
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                yield pb2.FileChunk(data=b"", path=path if sent == 0 else "", offset=sent, eof=True, context=ctx if sent == 0 else {})
                break
            yield pb2.FileChunk(data=b, path=path if sent == 0 else "", offset=sent, eof=False, context=ctx if sent == 0 else {})
            sent += len(b)

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=50055)
    ap.add_argument("--file", required=True)
    args = ap.parse_args()

    use_tls = os.getenv("RAKSHAK_TLS", "0") == "1"
    if use_tls:
        with open("client.crt", "rb") as f:
            creds = grpc.ssl_channel_credentials(f.read())
        ch = aio.secure_channel(f"{args.host}:{args.port}", creds)
    else:
        ch = aio.insecure_channel(f"{args.host}:{args.port}")

    async with ch:
        stub = pbg.DeciderStub(ch)
        resp = await stub.UploadAndDecide(gen_chunks(args.file, {}), metadata=auth_metadata())
        print(resp.decision)


if __name__ == "__main__":
    asyncio.run(main())
