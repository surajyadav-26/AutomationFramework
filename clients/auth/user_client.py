"""Client for the dummyjson auth endpoints."""

from __future__ import annotations

import requests

from core.api.http_client import HttpClient


class UserClient:
    def __init__(self, http: HttpClient):
        self.http = http

    def login(self, username: str, password: str) -> requests.Response:
        return self.http.post("/auth/login", json={"username": username, "password": password})
