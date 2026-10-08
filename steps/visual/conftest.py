"""Visual comparison fixtures."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Page

from core.browser.base_page import BasePage
from core.reporting.allure_helpers import attach_png
from core.settings import ROOT, Settings
from core.visual import baseline_store
from core.visual.comparator import MAX_DIFF_RATIO, compare
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
    request: pytest.FixtureRequest, page: Page, settings: Settings, browser_name: str
) -> Callable[..., None]:
    """Screenshot the current page and compare it with the stored baseline.

    The baseline is keyed by OS, browser and the page's current viewport, so a phone-sized and a
    desktop screenshot of the same page never share a file.
    """
    update = request.config.getoption("--update-baselines")

    def check(name: str, page_object: BasePage, max_ratio: float = MAX_DIFF_RATIO) -> None:
        viewport = page.viewport_size or {"width": 0, "height": 0}
        size = f"{viewport['width']}x{viewport['height']}"
        path = baseline_store.baseline_path(name, browser_name, viewport)
        actual = page_object.screenshot(
            mask=locators_for(page, getattr(page_object, "masked_selectors", ())),
            hide=getattr(page_object, "hidden_selectors", ()),
        )
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
        result = compare(
            actual,
            baseline,
            max_ratio=max_ratio,
            ignore_antialiasing=settings.visual_ignore_antialiasing,
        )
        if result.matches:
            return
        attach_png(baseline, "Baseline")
        attach_png(actual, "Actual")
        DIFF_DIR.mkdir(parents=True, exist_ok=True)
        stem = f"{name}-{browser_name}-{size}"
        (DIFF_DIR / f"{stem}-actual.png").write_bytes(actual)
        if result.diff_image:
            attach_png(result.diff_image, "Diff")
            (DIFF_DIR / f"{stem}-diff.png").write_bytes(result.diff_image)
        pytest.fail(f"visual mismatch for '{name}' ({size}): {result.reason}", pytrace=False)

    return check


@pytest.fixture(autouse=True)
def browser_matrix(browser_name: str) -> str:
    """Puts browser_name in the fixture closure so --browser X --browser Y runs every test on each.

    pytest-bdd requests `page` dynamically, which pytest-playwright cannot see at collection.
    """
    return browser_name
