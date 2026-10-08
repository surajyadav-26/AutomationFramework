"""In-process fake of the dummyjson auth endpoint, for offline runs (API_MODE=stub).

Mirrors the behaviour observed against the real service: POST /auth/login returns 200 with the
user body for the valid username and password, and 400 {"message": "Invalid credentials"}
otherwise. It proves the logic of the tests, not the real service; live mode stays the default.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

USER = {
    "id": 1,
    "username": "emilys",
    "email": "emily.johnson@x.dummyjson.com",
    "firstName": "Emily",
    "lastName": "Johnson",
    "gender": "female",
    "image": "https://dummyjson.com/icon/emilys/128",
}


class StubAuthServer:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        assert self._server, "stub server is not running"
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> StubAuthServer:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 (name required by BaseHTTPRequestHandler)
                # Always consume the request body first: replying and closing with unread data
                # can reset the connection under the client (seen on Windows as a flaky 404 test).
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                if self.path != "/auth/login":
                    return self._send(404, {"message": "Not Found"})
                try:
                    body = json.loads(raw or b"{}")
                except ValueError:
                    return self._send(400, {"message": "Invalid JSON"})
                valid = body.get("username") == owner.username
                valid = valid and body.get("password") == owner.password
                if valid:
                    return self._send(
                        200, {"accessToken": "stub-access", "refreshToken": "stub-refresh", **USER}
                    )
                return self._send(400, {"message": "Invalid credentials"})

            def _send(self, status: int, payload: dict) -> None:
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args) -> None:  # keep test output quiet
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
