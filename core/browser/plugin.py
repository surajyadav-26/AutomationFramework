"""pytest plugin: deterministic browser context and the data-test id attribute.

Registered by the root conftest.py (pytest_plugins).
"""

from __future__ import annotations

import pytest

from core.settings import LOCALE, TIMEZONE, VIEWPORT


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    """Fixed, deterministic rendering context for every browser test."""
    return {
        **browser_context_args,
        "viewport": dict(VIEWPORT),
        "locale": LOCALE,
        "timezone_id": TIMEZONE,
        "reduced_motion": "reduce",
    }


@pytest.fixture(scope="session")
def playwright(playwright):
    """pytest-playwright's driver, with data-test as the test id attribute (get_by_test_id)."""
    playwright.selectors.set_test_id_attribute("data-test")
    return playwright
