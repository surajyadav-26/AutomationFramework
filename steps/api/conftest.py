"""Fixtures for every area of the API suite."""

from __future__ import annotations

import pytest

from core.settings import Settings


@pytest.fixture(scope="session")
def api_base_url(settings: Settings) -> str:
    """The base URL of the API under test (API_URL from config/<TEST_ENV>.env)."""
    return settings.api_url
