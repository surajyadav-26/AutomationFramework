"""Page-object fixtures for the UI suite."""

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
