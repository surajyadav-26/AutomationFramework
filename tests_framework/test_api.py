"""API layer: HTTP client, schema validation and credential redaction."""

import json

import pytest
import requests

from core.api import http_client, validator
from core.api.http_client import DEFAULT_TIMEOUT, HttpClient
from core.api.redaction import MASK, redact
from core.api.validator import validate_schema


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


def make_response(status=200, body=b'{"ok": true}'):
    response = requests.Response()
    response.status_code = status
    response._content = body
    return response


def build(monkeypatch, response):
    attachments = []
    monkeypatch.setattr(http_client, "attach_json", lambda data, name: attachments.append(name))
    client = HttpClient("https://api.example/")
    client.session = FakeSession(response)
    return client, attachments


def test_url_is_joined_without_double_slash_and_timeout_defaults(monkeypatch):
    client, _ = build(monkeypatch, make_response())
    client.post("/items", json={"a": 1})
    method, url, kwargs = client.session.calls[0]
    assert (method, url) == ("POST", "https://api.example/items")
    assert kwargs["timeout"] == DEFAULT_TIMEOUT
    assert kwargs["json"] == {"a": 1}


def test_explicit_timeout_wins(monkeypatch):
    client, _ = build(monkeypatch, make_response())
    client.get("/x", timeout=1)
    assert client.session.calls[0][2]["timeout"] == 1


def test_request_and_response_are_attached(monkeypatch):
    client, attachments = build(monkeypatch, make_response(400))
    assert client.post("/items").status_code == 400
    assert attachments == ["Request POST /items", "Response 400 /items"]


def test_non_json_body_does_not_break_attachment(monkeypatch):
    client, attachments = build(monkeypatch, make_response(502, b"<html>bad gateway</html>"))
    assert client.get("/x").status_code == 502
    assert len(attachments) == 2


# --- schema validation ------------------------------------------------------------------------

SCHEMA = {
    "type": "object",
    "required": ["id", "name"],
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string", "minLength": 1},
    },
}


@pytest.fixture
def schema_dir(tmp_path, monkeypatch):
    """A throwaway test_data/schemas folder with one schema, so the tests own their data."""
    (tmp_path / "item.json").write_text(json.dumps(SCHEMA), encoding="utf-8")
    monkeypatch.setattr(validator, "SCHEMA_DIR", tmp_path)
    return tmp_path


def test_valid_body_passes(schema_dir):
    validate_schema({"id": 1, "name": "x"}, "item.json")


def test_missing_field_is_reported_by_name(schema_dir):
    with pytest.raises(AssertionError, match="name"):
        validate_schema({"id": 1}, "item.json")


def test_wrong_type_and_empty_value_are_reported_together(schema_dir):
    with pytest.raises(AssertionError) as error:
        validate_schema({"id": "1", "name": ""}, "item.json")
    assert "id" in str(error.value)
    assert "name" in str(error.value)


def test_an_unrelated_body_does_not_match(schema_dir):
    with pytest.raises(AssertionError, match="item.json"):
        validate_schema({"message": "Not found"}, "item.json")


def test_a_missing_schema_file_is_an_error_not_a_pass(schema_dir):
    with pytest.raises(FileNotFoundError):
        validate_schema({}, "nothing.json")


# --- redaction of credentials in attachments --------------------------------------------------


def test_sensitive_keys_are_masked_at_any_depth_and_case():
    data = {
        "username": "alice",
        "password": "hunter2",
        "Authorization": "Bearer abc",
        "nested": {"accessToken": "t", "refresh_token": "r", "items": [{"apiKey": "k", "ok": 1}]},
        "Set-Cookie": "sid=1",
    }
    assert redact(data) == {
        "username": "alice",
        "password": MASK,
        "Authorization": MASK,
        "nested": {
            "accessToken": MASK,
            "refresh_token": MASK,
            "items": [{"apiKey": MASK, "ok": 1}],
        },
        "Set-Cookie": MASK,
    }


def test_redaction_returns_a_copy_and_keeps_empty_values_visible():
    original = {"password": "x", "token": ""}
    result = redact(original)
    assert original == {"password": "x", "token": ""}
    assert result == {"password": MASK, "token": ""}


def test_non_sensitive_data_and_scalars_are_unchanged():
    assert redact({"id": 1, "tags": ["a", "b"]}) == {"id": 1, "tags": ["a", "b"]}
    assert redact("text") == "text"
    assert redact(None) is None


class AuthHeaderSession:
    def __init__(self, response):
        self.response = response
        self.headers = {"Authorization": "Bearer top-secret"}

    def request(self, method, url, **kwargs):
        return self.response


def test_the_http_client_never_attaches_credentials(monkeypatch):
    response = requests.Response()
    response.status_code = 200
    response._content = b'{"accessToken": "tok-123", "refreshToken": "ref-456", "id": 1}'
    attachments = []
    monkeypatch.setattr(http_client, "attach_json", lambda data, name: attachments.append(data))
    client = HttpClient("https://api.example")
    client.session = AuthHeaderSession(response)
    client.post("/login", json={"username": "u", "password": "pw-789"}, headers={"X-Api-Key": "k"})
    dump = repr(attachments)
    for secret in ("pw-789", "tok-123", "ref-456", "top-secret", "'k'"):
        assert secret not in dump
    assert dump.count(MASK) >= 5
    assert "'id': 1" in dump  # useful, non-sensitive data is still reported
