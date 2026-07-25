# Provides RAKSHAK support for conftest.
"""Integration test configuration and fixtures."""
import asyncio, pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from httpx import AsyncClient
from backend.api.main import app

@pytest.fixture
async def client():
    """Create async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
