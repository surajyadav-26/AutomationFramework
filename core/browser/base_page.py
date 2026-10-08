"""Base class for page objects."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

from playwright.sync_api import Locator, Page, expect

# Hides the text caret and stops CSS animations/transitions for stable screenshots.
_STABILISE_CSS = """
*, *::before, *::after {
    animation: none !important;
    transition: none !important;
    caret-color: transparent !important;
}
"""


def hide_css(selectors: Iterable[str]) -> str:
    """CSS that makes the elements invisible but keeps their space, so layout is unchanged."""
    return "\n".join(f"{selector} {{ visibility: hidden !important; }}" for selector in selectors)


class BasePage:
    path = "/"

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url.rstrip("/")
        self.log = logging.getLogger(f"ui.{type(self).__name__}")

    def open(self) -> None:
        url = self.base_url + self.path
        self.log.info("open %s", url)
        self.page.goto(url)

    def resize(self, width: int, height: int) -> None:
        self.log.info("resize viewport to %dx%d", width, height)
        self.page.set_viewport_size({"width": width, "height": height})

    def by_test(self, test_id: str) -> Locator:
        """Locator by test id; the attribute is configured as data-test in the root conftest."""
        return self.page.get_by_test_id(test_id)

    def expect_url_contains(self, fragment: str) -> None:
        self.log.info("expect url contains %r", fragment)
        expect(self.page).to_have_url(re.compile(re.escape(fragment)))

    def wait_until_rendered(self) -> None:
        """Wait for what changes pixels: the load event, web fonts and every image.

        Playwright discourages "networkidle": a page that keeps polling never reaches it.
        """
        self.page.wait_for_load_state("load")
        self.page.evaluate("document.fonts.ready.then(() => true)")
        self.page.wait_for_function("Array.from(document.images).every(image => image.complete)")

    def screenshot(self, mask: list[Locator] | None = None, hide: Iterable[str] = ()) -> bytes:
        """Viewport PNG with animations disabled and the caret hidden.

        mask: locators painted over with a solid box (the box follows the element size).
        hide: CSS selectors made invisible in place (use for text whose width changes).
        """
        hide = list(hide)
        self.log.info("screenshot (%d masked, %d hidden selector(s))", len(mask or []), len(hide))
        self.page.add_style_tag(content=_STABILISE_CSS)
        self.wait_until_rendered()
        return self.page.screenshot(
            animations="disabled", caret="hide", mask=mask or [], style=hide_css(hide) or None
        )
