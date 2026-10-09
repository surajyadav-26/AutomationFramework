"""Saucedemo products (inventory) page shown after login."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from core.browser.base_page import BasePage
from pages.components.header import Header


class DashboardPage(BasePage):
    path = "/inventory.html"
    # visual_user gets randomised prices on every load. Hiding (not masking) them keeps the
    # layout and the Add to cart buttons in the screenshot; only the price text is left out.
    hidden_selectors = ('[data-test="inventory-item-price"]',)

    def __init__(self, page: Page, base_url: str):
        super().__init__(page, base_url)
        self.header = Header(page)

    def expect_loaded(self) -> None:
        self.log.info("expect products page loaded")
        self.expect_url_contains("/inventory.html")
        self.header.expect_loaded()
        expect(self.by_test("title")).to_have_text("Products")
        expect(self.by_test("inventory-list")).to_be_visible()
        expect(self.by_test("inventory-item").first).to_be_visible()
