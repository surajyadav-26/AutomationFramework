"""requests wrapper that logs every call and attaches request/response to Allure."""

from __future__ import annotations

import logging

import requests

from core.reporting.allure_helpers import attach_json

log = logging.getLogger("api")
DEFAULT_TIMEOUT = 15


class HttpClient:
    def __init__(self, base_url: str, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = self.base_url + path
        kwargs.setdefault("timeout", self.timeout)
        log.info("%s %s", method, url)
        attach_json(
            {
                "method": method,
                "url": url,
                "headers": dict(self.session.headers),
                "json": kwargs.get("json"),
            },
            f"Request {method} {path}",
        )
        response = self.session.request(method, url, **kwargs)
        log.info("-> %s in %.0f ms", response.status_code, response.elapsed.total_seconds() * 1000)
        attach_json(
            {
                "status": response.status_code,
                "headers": dict(response.headers),
                "body": _body(response),
            },
            f"Response {response.status_code} {path}",
        )
        return response

    def post(self, path: str, **kwargs) -> requests.Response:
        return self.request("POST", path, **kwargs)

    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)


def _body(response: requests.Response) -> object:
    try:
        return response.json()
    except ValueError:
        return response.text
