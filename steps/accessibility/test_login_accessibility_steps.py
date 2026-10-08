"""Step definitions for features/accessibility/auth/login_accessibility.feature."""

from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when

from core.data.factories import username_for

scenarios("accessibility/login_accessibility.feature")


@given("I am viewing the login page")
def _open_login_page(login_page):
    login_page.open()
    login_page.expect_loaded()


@when(parsers.parse('I sign in as the "{role}" user'))
def _sign_in(login_page, dashboard_page, settings, role):
    login_page.login(username_for(role), settings.app_password)
    dashboard_page.expect_loaded()


@then("the login page has no blocking accessibility violations")
def _login_page_accessible(assert_accessible):
    assert_accessible("login page")


@then("the inventory page has no blocking accessibility violations")
def _inventory_page_accessible(assert_accessible):
    assert_accessible("inventory page")
