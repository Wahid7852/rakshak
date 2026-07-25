# Provides RAKSHAK support for main.
from fastapi import FastAPI, Depends, Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .routers import health, scan, logs, quarantine
from .config import settings
from .security.auth import verify_api_key
from .security.rate_limit import limiter
from .schemas import HealthResponse
from backend.observability.metrics import render_latest

app = FastAPI(title=settings.app_name, version=settings.version)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)

@app.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok", "service": settings.app_name, "version": settings.version}

@app.get("/metrics")
def metrics():
    body, content_type = render_latest()
    return Response(content=body, media_type=content_type)

app.include_router(health.router, prefix="/v1", tags=["health"])
app.include_router(scan.router, prefix="/v1", tags=["scan"], dependencies=[Depends(verify_api_key)])
app.include_router(logs.router, prefix="/v1", tags=["logs"], dependencies=[Depends(verify_api_key)])
app.include_router(quarantine.router, prefix="/v1", tags=["quarantine"], dependencies=[Depends(verify_api_key)])
