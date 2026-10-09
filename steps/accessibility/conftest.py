"""Fixtures for every area of the accessibility suite: the axe check."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Page

from core.accessibility.axe_scanner import blocking, describe, scan
from core.settings import Settings
from shared.browser_fixtures import browser_matrix  # noqa: F401


@pytest.fixture
def assert_accessible(page: Page, settings: Settings) -> Callable[[str], None]:
    """Scan the current page; fail on violations at or above A11Y_FAIL_IMPACT."""

    def check(name: str) -> None:
        violations = scan(page, settings.a11y_include_best_practices)
        failing = blocking(violations, settings.a11y_fail_impact)
        assert not failing, (
            f"{name}: {len(failing)} accessibility violation(s) at "
            f"'{settings.a11y_fail_impact}' or worse: {describe(failing)}"
        )

    return check
