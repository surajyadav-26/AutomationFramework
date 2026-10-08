"""Saucedemo login page."""

from __future__ import annotations

from playwright.sync_api import expect

from core.browser.base_page import BasePage


class LoginPage(BasePage):
    path = "/"

    def login(self, username: str, password: str) -> None:
        self.by_test("username").fill(username)
        self.by_test("password").fill(password)
        self.by_test("login-button").click()

    def expect_error(self, message: str) -> None:
        expect(self.by_test("error")).to_have_text(message)

    def expect_loaded(self) -> None:
        expect(self.by_test("login-button")).to_be_visible()
