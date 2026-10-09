"""Fixtures shared by all suites. (Hooks live in core.reporting.plugin.)"""

from __future__ import annotations

import pytest

from core.data.cleanup import Cleanup
from core.settings import Settings, get_settings


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(autouse=True)
def cleanup():
    """Registry of teardown callbacks; they run even when the test failed."""
    registry = Cleanup()
    yield registry
    failures = registry.run_all()
    assert not failures, f"cleanup callbacks failed: {failures}"
