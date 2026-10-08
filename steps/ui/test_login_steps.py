"""Step definitions for features/ui/auth/login.feature."""

from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when

from core.data.factories import random_password, username_for

scenarios("ui/login.feature")


@given("I am on the login page")
def _open_login_page(login_page):
    login_page.open()
    login_page.expect_loaded()


@when(parsers.parse('I log in as the "{role}" user with a {password_kind} password'))
def _log_in(login_page, settings, role, password_kind):
    password = settings.app_password if password_kind == "valid" else random_password()
    login_page.login(username_for(role), password)


@then("I see the products page")
def _products_page_shown(dashboard_page):
    dashboard_page.expect_loaded()


@then(parsers.parse('I see the login error "{message}"'))
def _login_error_shown(login_page, message):
    login_page.expect_error(message)
