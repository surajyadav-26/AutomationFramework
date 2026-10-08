"""Base class for page objects."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

# Hides the text caret and stops CSS animations/transitions for stable screenshots.
_STABILISE_CSS = """
*, *::before, *::after {
    animation: none !important;
    transition: none !important;
    caret-color: transparent !important;
}
"""


class BasePage:
    path = "/"

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url.rstrip("/")

    def open(self) -> None:
        self.page.goto(self.base_url + self.path)

    def by_test(self, test_id: str) -> Locator:
        """Locator by test id; the attribute is configured as data-test in the root conftest."""
        return self.page.get_by_test_id(test_id)

    def expect_url_contains(self, fragment: str) -> None:
        expect(self.page).to_have_url(re.compile(re.escape(fragment)))

    def screenshot(self, mask: list[Locator] | None = None) -> bytes:
        """Viewport PNG with animations disabled, caret hidden and optional masked areas."""
        self.page.add_style_tag(content=_STABILISE_CSS)
        self.page.wait_for_load_state("networkidle")
        return self.page.screenshot(animations="disabled", caret="hide", mask=mask or [])
