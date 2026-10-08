"""Steps shared by the visual and accessibility suites.

Import them into a suite's step module to use them:
    from steps._login_steps import *  # noqa: F403
pytest-bdd registers a step in the module that defines it, so a plain import of the functions is
not enough; the star import also brings in the registered step fixtures.
"""

from __future__ import annotations

from pytest_bdd import given, parsers, when

from core.data.factories import username_for


@given("I am viewing the login page")
def open_login_page(login_page):
    login_page.open()
    login_page.expect_loaded()


@when(parsers.parse('I sign in as the "{role}" user'))
def sign_in(login_page, dashboard_page, settings, role):
    login_page.login(username_for(role), settings.app_password)
    dashboard_page.expect_loaded()
