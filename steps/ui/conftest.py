"""Page-object fixtures for the UI suite."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from core.settings import Settings
from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage


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
