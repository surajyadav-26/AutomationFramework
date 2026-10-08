"""Client fixtures for the API suite."""

from __future__ import annotations

import pytest

from clients.auth.user_client import UserClient
from core.api.http_client import HttpClient
from core.settings import Settings


@pytest.fixture
def user_client(settings: Settings) -> UserClient:
    return UserClient(HttpClient(settings.api_url))


@pytest.fixture
def response_holder() -> dict:
    """Carries the last response from a When step to the Then steps."""
    return {}
