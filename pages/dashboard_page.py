"""Saucedemo products (inventory) page shown after login."""

from __future__ import annotations

from playwright.sync_api import expect

from core.browser.base_page import BasePage


class DashboardPage(BasePage):
    path = "/inventory.html"
    # visual_user gets randomised prices on every load and the price box width follows the
    # text, so the whole (fixed-width) price bar is masked, Add to cart buttons included.
    volatile_selectors = (".pricebar",)

    def expect_loaded(self) -> None:
        self.log.info("expect products page loaded")
        self.expect_url_contains("/inventory.html")
        expect(self.by_test("title")).to_have_text("Products")
        expect(self.by_test("inventory-list")).to_be_visible()
        expect(self.by_test("inventory-item").first).to_be_visible()
