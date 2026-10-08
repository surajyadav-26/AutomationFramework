"""Saucedemo login page."""

from __future__ import annotations

from playwright.sync_api import expect

from core.browser.base_page import BasePage


class LoginPage(BasePage):
    path = "/"

    @property
    def login_button(self):
        return self.page.get_by_role("button", name="Login", exact=True)

    def login(self, username: str, password: str) -> None:
        self.page.get_by_label("Username", exact=True).fill(username)
        self.page.get_by_label("Password", exact=True).fill(password)
        self.login_button.click()

    def expect_error(self, message: str) -> None:
        expect(self.by_test("error")).to_have_text(message)

    def expect_loaded(self) -> None:
        expect(self.login_button).to_be_visible()
