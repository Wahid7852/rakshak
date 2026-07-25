# Builds the RAKSHAK backend: HTTP and gRPC APIs, bwrap-isolated sandbox analysis.
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        bubblewrap \
        strace \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

# `pip install .` (non-editable) copies the package into site-packages, so
# quarantine/checkpoint state can't live at its dev-mode default path (inside
# the installed package tree, owned by root) - give it a dedicated writable
# directory instead of chowning the whole install
RUN useradd --create-home --uid 1000 rakshak \
    && mkdir -p /app/var/quarantine /app/var/state \
    && chown -R rakshak:rakshak /app/var
USER rakshak

# defaults are loopback-only, which is right for local dev but useless behind
# a container's network namespace, so bind wide here and let the operator
# firewall the exposed ports instead
ENV RAKSHAK_HTTP_HOST=0.0.0.0 \
    RAKSHAK_GRPC_HOST=0.0.0.0 \
    RAKSHAK_QUARANTINE_DIR=/app/var/quarantine \
    RAKSHAK_MODEL_STATE_DIR=/app/var/state

EXPOSE 8080 50055

CMD ["rakshak-http"]
