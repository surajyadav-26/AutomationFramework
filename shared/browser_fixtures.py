"""Fixtures shared by the browser suites (ui, visual, accessibility).

Each suite conftest re-exports what it needs:
    from shared.browser_fixtures import browser_matrix, dashboard_page, login_page  # noqa: F401
They live here, and not in steps/conftest.py, so the API suite never sees browser fixtures.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from core.settings import Settings
from pages.auth.dashboard_page import DashboardPage
from pages.auth.login_page import LoginPage


@pytest.fixture
def login_page(page: Page, settings: Settings) -> LoginPage:
    return LoginPage(page, settings.app_url)


@pytest.fixture
def dashboard_page(page: Page, settings: Settings) -> DashboardPage:
    return DashboardPage(page, settings.app_url)


@pytest.fixture(autouse=True)
def browser_matrix(browser_name: str) -> str:
    """Puts browser_name in the fixture closure so --browser X --browser Y runs every test on each.

    pytest-bdd requests `page` dynamically, which pytest-playwright cannot see at collection.
    """
    return browser_name
