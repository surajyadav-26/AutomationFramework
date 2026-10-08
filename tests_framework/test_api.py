"""API layer: HTTP client, offline stub server, schema validation and credential redaction."""

import pytest
import requests

from core.api import http_client
from core.api.http_client import DEFAULT_TIMEOUT, HttpClient
from core.api.redaction import MASK, redact
from core.api.stub_server import StubAuthServer
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
    client.post("/auth/login", json={"a": 1})
    method, url, kwargs = client.session.calls[0]
    assert (method, url) == ("POST", "https://api.example/auth/login")
    assert kwargs["timeout"] == DEFAULT_TIMEOUT
    assert kwargs["json"] == {"a": 1}


def test_explicit_timeout_wins(monkeypatch):
    client, _ = build(monkeypatch, make_response())
    client.get("/x", timeout=1)
    assert client.session.calls[0][2]["timeout"] == 1


def test_request_and_response_are_attached(monkeypatch):
    client, attachments = build(monkeypatch, make_response(400))
    assert client.post("/auth/login").status_code == 400
    assert attachments == ["Request POST /auth/login", "Response 400 /auth/login"]


def test_non_json_body_does_not_break_attachment(monkeypatch):
    client, attachments = build(monkeypatch, make_response(502, b"<html>bad gateway</html>"))
    assert client.get("/x").status_code == 502
    assert len(attachments) == 2


# --- offline stub server ----------------------------------------------------------------------


@pytest.fixture
def stub():
    server = StubAuthServer("emilys", "right-password").start()
    yield server
    server.stop()


def login(stub, username, password):
    return requests.post(
        stub.url + "/auth/login", json={"username": username, "password": password}, timeout=5
    )


def test_valid_credentials_return_a_body_that_matches_the_real_schema(stub):
    response = login(stub, "emilys", "right-password")
    assert response.status_code == 200
    validate_schema(response.json(), "user_schema.json")
    assert response.json()["accessToken"]


def test_wrong_password_returns_the_observed_error(stub):
    response = login(stub, "emilys", "wrong")
    assert response.status_code == 400
    assert response.json() == {"message": "Invalid credentials"}


def test_unknown_user_is_rejected(stub):
    assert login(stub, "nobody", "right-password").status_code == 400


def test_unknown_path_is_404(stub):
    assert requests.post(stub.url + "/nope", json={}, timeout=5).status_code == 404


def test_invalid_json_is_a_400_not_a_crash(stub):
    response = requests.post(stub.url + "/auth/login", data=b"{not json", timeout=5)
    assert response.status_code == 400


def test_servers_use_free_ports_and_stop_cleanly():
    first = StubAuthServer("a", "b").start()
    second = StubAuthServer("a", "b").start()
    first_url = first.url
    try:
        assert first_url != second.url
    finally:
        first.stop()
        second.stop()
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get(first_url, timeout=2)


# --- schema validation ------------------------------------------------------------------------


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


# --- redaction of credentials in attachments --------------------------------------------------


def test_sensitive_keys_are_masked_at_any_depth_and_case():
    data = {
        "username": "emilys",
        "password": "hunter2",
        "Authorization": "Bearer abc",
        "nested": {"accessToken": "t", "refresh_token": "r", "items": [{"apiKey": "k", "ok": 1}]},
        "Set-Cookie": "sid=1",
    }
    assert redact(data) == {
        "username": "emilys",
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
    import requests

    response = requests.Response()
    response.status_code = 200
    response._content = b'{"accessToken": "tok-123", "refreshToken": "ref-456", "id": 1}'
    attachments = []
    monkeypatch.setattr(http_client, "attach_json", lambda data, name: attachments.append(data))
    client = HttpClient("https://api.example")
    client.session = AuthHeaderSession(response)
    client.post(
        "/auth/login", json={"username": "u", "password": "pw-789"}, headers={"X-Api-Key": "k"}
    )
    dump = repr(attachments)
    for secret in ("pw-789", "tok-123", "ref-456", "top-secret", "'k'"):
        assert secret not in dump
    assert dump.count(MASK) >= 5
    assert "'id': 1" in dump  # useful, non-sensitive data is still reported
