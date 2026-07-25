# Runs the active unary gRPC client from the legacy command path.
from backend.api.gRPC.clients.cli_decide import main


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
