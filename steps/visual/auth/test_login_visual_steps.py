"""Step definitions for features/visual/auth/login_visual.feature."""

from __future__ import annotations

from pytest_bdd import given, parsers, scenarios, then, when

from core.data.factories import username_for

scenarios("visual/auth/login_visual.feature")


@given("I am viewing the login page")
def _open_login_page(login_page):
    login_page.open()
    login_page.expect_loaded()


@when(parsers.parse('I sign in as the "{role}" user'))
def _sign_in(login_page, dashboard_page, settings, role):
    login_page.login(username_for(role), settings.app_password)
    dashboard_page.expect_loaded()


@then("the login page matches the baseline")
def _login_page_matches_baseline(assert_matches_baseline, login_page):
    assert_matches_baseline("login_page", login_page)


@then("the inventory page matches the baseline")
def _inventory_page_matches_baseline(assert_matches_baseline, dashboard_page):
    assert_matches_baseline("inventory_page", dashboard_page)
