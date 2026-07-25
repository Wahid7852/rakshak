# Provides a gRPC client for cli decide workflows.
import argparse, asyncio, os, grpc
from grpc import aio
from backend.api.gRPC.clients.common import auth_metadata
from backend.api.gRPC.stubs import pb2, pbg


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=50055)
    ap.add_argument("--kind", choices=["log", "file"], required=True)
    ap.add_argument("--text", help="log line text")
    ap.add_argument("--file", help="path to file to read (bytes)")
    args = ap.parse_args()

    # Optional TLS
    use_tls = os.getenv("RAKSHAK_TLS", "0") == "1"
    if use_tls:
        with open("client.crt", "rb") as f:
            creds = grpc.ssl_channel_credentials(f.read())
        ch = aio.secure_channel(f"{args.host}:{args.port}", creds)
    else:
        ch = aio.insecure_channel(f"{args.host}:{args.port}")

    async with ch:
        stub = pbg.DeciderStub(ch)
        if args.kind == "log":
            req = pb2.DecideRequest(event=pb2.Event(kind=0, text=args.text or ""))
        else:
            data = b""
            if args.file:
                with open(args.file, "rb") as f:
                    data = f.read()
            req = pb2.DecideRequest(event=pb2.Event(kind=1, bytes=data, path=args.file or ""))
        resp = await stub.Decide(req, metadata=auth_metadata())
        print(resp.decision)


if __name__ == "__main__":
    asyncio.run(main())
