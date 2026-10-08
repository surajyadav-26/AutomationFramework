"""Step definitions for features/accessibility/auth/login_accessibility.feature."""

from __future__ import annotations

from pytest_bdd import scenarios, then

from steps._login_steps import *  # noqa: F403  (pytest-bdd registers steps per module)

scenarios("accessibility/login_accessibility.feature")


@then("the login page has no blocking accessibility violations")
def _login_page_accessible(assert_accessible):
    assert_accessible("login page")


@then("the inventory page has no blocking accessibility violations")
def _inventory_page_accessible(assert_accessible):
    assert_accessible("inventory page")
