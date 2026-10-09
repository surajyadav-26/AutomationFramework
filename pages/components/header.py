"""The header bar shown on every page of the shop: logo, menu button and cart link."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from core.browser.base_component import BaseComponent


class Header(BaseComponent):
    def __init__(self, page: Page):
        super().__init__(page.get_by_test_id("primary-header"))

    @property
    def logo(self) -> Locator:
        return self.root.get_by_text("Swag Labs", exact=True)

    @property
    def menu_button(self) -> Locator:
        return self.root.get_by_role("button", name="Open Menu")

    @property
    def cart_link(self) -> Locator:
        return self.by_test("shopping-cart-link")

    def expect_loaded(self) -> None:
        self.log.info("expect the header with logo, menu and cart")
        self.expect_visible()
        expect(self.logo).to_be_visible()
        expect(self.menu_button).to_be_visible()
        expect(self.cart_link).to_be_visible()
