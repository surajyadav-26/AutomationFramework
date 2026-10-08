"""core.api.stub_server: the offline fake of the auth endpoint."""

import pytest
import requests

from core.api.stub_server import StubAuthServer
from core.api.validator import validate_schema


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
