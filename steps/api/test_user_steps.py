"""Step definitions for features/api/user.feature."""

from __future__ import annotations

from pytest_bdd import parsers, scenarios, then, when

from core.api.validator import validate_schema
from core.data.factories import random_password, username_for

scenarios("api/user.feature")


@when("I request a token with valid credentials", target_fixture="response")
def _login_valid(user_client, settings):
    return user_client.login(username_for("api"), settings.api_password)


@when("I request a token with a wrong password", target_fixture="response")
def _login_wrong_password(user_client):
    return user_client.login(username_for("api"), random_password())


@then(parsers.parse("the response status is {status:d}"))
def _status_is(response, status):
    assert response.status_code == status


@then("the response body matches the user schema")
def _body_matches_schema(response):
    validate_schema(response.json(), "user_schema.json")


@then("the response contains an access token")
def _has_access_token(response):
    assert response.json().get("accessToken")


@then(parsers.parse('the response message is "{message}"'))
def _message_is(response, message):
    assert response.json()["message"] == message
