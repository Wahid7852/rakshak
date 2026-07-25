# Defines backend API routes for health.
from fastapi import APIRouter

from backend.api.config import settings
from backend.api.schemas import HealthResponse

router = APIRouter()

@router.get("/healthz", response_model=HealthResponse)
def healthz():
    return {"status": "ok", "service": settings.app_name, "version": settings.version}
