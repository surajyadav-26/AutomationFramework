"""core.api.validator against the real user schema."""

import pytest

from core.api.validator import validate_schema

VALID = {
    "accessToken": "a",
    "refreshToken": "r",
    "id": 1,
    "username": "u",
    "email": "e",
    "firstName": "f",
    "lastName": "l",
    "gender": "female",
    "image": "i",
}


def test_valid_body_passes():
    validate_schema(VALID, "user_schema.json")


def test_missing_field_is_reported_by_name():
    body = {k: v for k, v in VALID.items() if k != "accessToken"}
    with pytest.raises(AssertionError, match="accessToken"):
        validate_schema(body, "user_schema.json")


def test_wrong_type_and_empty_token_are_reported_together():
    body = {**VALID, "id": "1", "accessToken": ""}
    with pytest.raises(AssertionError) as error:
        validate_schema(body, "user_schema.json")
    assert "id" in str(error.value)
    assert "accessToken" in str(error.value)


def test_error_body_does_not_match_the_success_schema():
    with pytest.raises(AssertionError):
        validate_schema({"message": "Invalid credentials"}, "user_schema.json")
