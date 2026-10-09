"""Fixtures of the auth area (API suite)."""

from __future__ import annotations

import pytest

from clients.auth.user_client import UserClient
from core.api.http_client import HttpClient
from core.settings import Settings


@pytest.fixture
def user_client(api_base_url: str, settings: Settings) -> UserClient:
    return UserClient(HttpClient(api_base_url, timeout=settings.api_timeout))
