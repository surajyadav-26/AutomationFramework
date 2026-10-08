"""Accessibility fixtures."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Page

from core.accessibility.axe_scanner import blocking, describe, scan
from core.settings import Settings
from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage


@pytest.fixture
def login_page(page: Page, settings: Settings) -> LoginPage:
    return LoginPage(page, settings.app_url)


@pytest.fixture
def dashboard_page(page: Page, settings: Settings) -> DashboardPage:
    return DashboardPage(page, settings.app_url)


@pytest.fixture
def assert_accessible(page: Page, settings: Settings) -> Callable[[str], None]:
    """Scan the current page; fail on violations at or above A11Y_FAIL_IMPACT."""

    def check(name: str) -> None:
        violations = scan(page)
        failing = blocking(violations, settings.a11y_fail_impact)
        assert not failing, (
            f"{name}: {len(failing)} accessibility violation(s) at "
            f"'{settings.a11y_fail_impact}' or worse: {describe(failing)}"
        )

    return check


@pytest.fixture(autouse=True)
def browser_matrix(browser_name: str) -> str:
    """Puts browser_name in the fixture closure so --browser X --browser Y runs every test on each.

    pytest-bdd requests `page` dynamically, which pytest-playwright cannot see at collection.
    """
    return browser_name
