"""requests wrapper that logs every call and attaches request/response to Allure.

Everything attached is passed through redact(): passwords, tokens, cookies and authorization
headers never reach the report (which may be published) or the logs.
"""

from __future__ import annotations

import logging

import requests

from core.api.redaction import redact
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
            redact(
                {
                    "method": method,
                    "url": url,
                    "headers": {**self.session.headers, **(kwargs.get("headers") or {})},
                    "params": kwargs.get("params"),
                    "json": kwargs.get("json"),
                    "data": kwargs.get("data") if isinstance(kwargs.get("data"), dict) else None,
                }
            ),
            f"Request {method} {path}",
        )
        response = self.session.request(method, url, **kwargs)
        log.info("-> %s in %.0f ms", response.status_code, response.elapsed.total_seconds() * 1000)
        attach_json(
            redact(
                {
                    "status": response.status_code,
                    "headers": dict(response.headers),
                    "body": _body(response),
                }
            ),
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
