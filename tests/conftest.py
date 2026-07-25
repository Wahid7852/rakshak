# Provides RAKSHAK support for conftest.
"""Root test configuration."""
import os, sys, uuid
from pathlib import Path

# Add project root to Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

def pytest_configure(config):
    """Configure test markers."""
    if not config.option.basetemp:
        basetemp = root_dir / ".pytest-tmp" / f"run-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        basetemp.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(basetemp)

    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow running tests")

def pytest_collection_modifyitems(items):
    """Add markers based on directory structure."""
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker("unit")
        elif "integration" in str(item.fspath):
            item.add_marker("integration")
        elif "e2e" in str(item.fspath):
            item.add_marker("e2e")
