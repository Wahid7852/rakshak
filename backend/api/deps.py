# Shared singletons for FastAPI dependency wiring.
from functools import lru_cache

from backend.api.config import settings
from backend.engine.quarantine import QuarantineManager


@lru_cache(maxsize=1)
def get_quarantine_manager() -> QuarantineManager:
    return QuarantineManager(settings.quarantine_dir)
