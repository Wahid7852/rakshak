# Implements gRPC backend support for server.
"""Compatibility wrapper for the current gRPC decider server."""

from backend.api.gRPC.decider_server import DeciderService, main, serve

__all__ = ["DeciderService", "main", "serve"]


if __name__ == "__main__":
    main()
