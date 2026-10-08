"""core.api.http_client without any network."""

import requests

from core.api import http_client
from core.api.http_client import DEFAULT_TIMEOUT, HttpClient


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
