"""Step definitions for features/visual/auth/login_visual.feature."""

from __future__ import annotations

from pytest_bdd import given, scenarios, then

from core.settings import PHONE_VIEWPORT
from shared.login_steps import *  # noqa: F403  (pytest-bdd registers steps per module)

scenarios("visual/auth/login_visual.feature")


@given("I am using a phone-sized screen")
def _use_phone_screen(login_page):
    login_page.resize(PHONE_VIEWPORT["width"], PHONE_VIEWPORT["height"])


@then("the login page matches the baseline")
def _login_page_matches_baseline(assert_matches_baseline, login_page):
    assert_matches_baseline("login_page", login_page)


@then("the inventory page matches the baseline")
def _inventory_page_matches_baseline(assert_matches_baseline, dashboard_page):
    assert_matches_baseline("inventory_page", dashboard_page)
