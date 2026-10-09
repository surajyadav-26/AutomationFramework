"""Fixture shared by all browser suites (ui, visual, accessibility).

Each suite's conftest.py re-exports it:
    from shared.browser_fixtures import browser_matrix  # noqa: F401
It lives here, and not in steps/conftest.py, so the API suite never gets it.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def browser_matrix(browser_name: str) -> str:
    """Puts browser_name in the fixture closure so --browser X --browser Y runs every test on each.

    pytest-bdd requests `page` dynamically, which pytest-playwright cannot see at collection.
    """
    return browser_name
