"""Fixtures for every area of the API suite."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from core.api.stub_server import StubAuthServer
from core.data.factories import username_for
from core.settings import Settings


@pytest.fixture(scope="session")
def api_base_url(settings: Settings) -> Iterator[str]:
    """The real service (API_MODE=live, default) or an in-process stub (API_MODE=stub)."""
    if settings.api_mode == "live":
        yield settings.api_url
        return
    stub = StubAuthServer(username_for("api"), settings.api_password).start()
    try:
        yield stub.url
    finally:
        stub.stop()
