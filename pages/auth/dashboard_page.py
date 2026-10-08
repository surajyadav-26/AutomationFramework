"""Saucedemo products (inventory) page shown after login."""

from __future__ import annotations

from playwright.sync_api import expect

from core.browser.base_page import BasePage


class DashboardPage(BasePage):
    path = "/inventory.html"

    def expect_loaded(self) -> None:
        self.expect_url_contains("/inventory.html")
        expect(self.by_test("title")).to_have_text("Products")
        expect(self.by_test("inventory-list")).to_be_visible()
        expect(self.by_test("inventory-item").first).to_be_visible()
