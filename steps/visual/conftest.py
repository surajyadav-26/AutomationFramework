"""Visual comparison fixtures."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import pytest
from playwright.sync_api import Page

from core.browser.base_page import BasePage
from core.reporting.allure_helpers import attach_png
from core.settings import ROOT, VIEWPORT, Settings
from core.visual import baseline_store
from core.visual.comparator import compare
from core.visual.masking import locators_for
from pages.dashboard_page import DashboardPage
from pages.login_page import LoginPage

DIFF_DIR = ROOT / "reports" / "visual"


@pytest.fixture
def login_page(page: Page, settings: Settings) -> LoginPage:
    return LoginPage(page, settings.app_url)


@pytest.fixture
def dashboard_page(page: Page, settings: Settings) -> DashboardPage:
    return DashboardPage(page, settings.app_url)


@pytest.fixture
def assert_matches_baseline(
    request: pytest.FixtureRequest, page: Page, browser_name: str
) -> Callable[..., None]:
    """Screenshot the current page and compare it with the stored baseline."""
    update = request.config.getoption("--update-baselines")

    def check(name: str, page_object: BasePage) -> None:
        mask_selectors: Iterable[str] = getattr(page_object, "volatile_selectors", ())
        path = baseline_store.baseline_path(name, browser_name, VIEWPORT)
        actual = page_object.screenshot(mask=locators_for(page, mask_selectors))
        if update:
            baseline_store.save(path, actual)
            return
        if not path.exists():
            attach_png(actual, "Actual")
            pytest.fail(
                f"no baseline for '{name}' at {path}. "
                "Generate it with: pytest steps/visual --update-baselines",
                pytrace=False,
            )
        baseline = path.read_bytes()
        result = compare(actual, baseline)
        if result.matches:
            return
        attach_png(baseline, "Baseline")
        attach_png(actual, "Actual")
        DIFF_DIR.mkdir(parents=True, exist_ok=True)
        (DIFF_DIR / f"{name}-actual.png").write_bytes(actual)
        if result.diff_image:
            attach_png(result.diff_image, "Diff")
            (DIFF_DIR / f"{name}-diff.png").write_bytes(result.diff_image)
        pytest.fail(f"visual mismatch for '{name}': {result.reason}", pytrace=False)

    return check


@pytest.fixture(autouse=True)
def browser_matrix(browser_name: str) -> str:
    """Puts browser_name in the fixture closure so --browser X --browser Y runs every test on each.

    pytest-bdd requests `page` dynamically, which pytest-playwright cannot see at collection.
    """
    return browser_name
