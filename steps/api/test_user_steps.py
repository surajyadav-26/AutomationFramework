"""Step definitions for features/api/auth/user.feature."""

from __future__ import annotations

from pytest_bdd import parsers, scenarios, then, when

from core.api.validator import validate_schema
from core.data.factories import random_password, username_for

scenarios("api/user.feature")


@when("I request a token with valid credentials")
def _login_valid(user_client, settings, response_holder):
    response_holder["response"] = user_client.login(username_for("api"), settings.api_password)


@when("I request a token with a wrong password")
def _login_wrong_password(user_client, response_holder):
    response_holder["response"] = user_client.login(username_for("api"), random_password())


@then(parsers.parse("the response status is {status:d}"))
def _status_is(response_holder, status):
    assert response_holder["response"].status_code == status


@then("the response body matches the user schema")
def _body_matches_schema(response_holder):
    validate_schema(response_holder["response"].json(), "user_schema.json")


@then("the response contains an access token")
def _has_access_token(response_holder):
    assert response_holder["response"].json().get("accessToken")


@then(parsers.parse('the response message is "{message}"'))
def _message_is(response_holder, message):
    assert response_holder["response"].json()["message"] == message
