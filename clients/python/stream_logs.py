# Runs the active log-stream gRPC client from the legacy command path.
from backend.api.gRPC.clients.stream_logs import main


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
