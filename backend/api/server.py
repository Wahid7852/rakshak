# Starts the production HTTP API from environment-backed settings.
import os, uvicorn

from backend.observability.request_id import configure_json_logging


def main() -> None:
    configure_json_logging()
    uvicorn.run(
        "backend.api.main:app",
        host=os.getenv("RAKSHAK_HTTP_HOST", "127.0.0.1"),
        port=int(os.getenv("RAKSHAK_HTTP_PORT", "8080")),
        log_level=os.getenv("RAKSHAK_LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
