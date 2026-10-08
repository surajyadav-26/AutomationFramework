"""Masks credentials before request/response data is attached to reports or logs."""

from __future__ import annotations

import re
from typing import Any

MASK = "***"
# Matches parts of key names: password, passwd, secret, token (accessToken, refresh_token),
# authorization, api key, cookie (Cookie, Set-Cookie).
SENSITIVE_KEY = re.compile(r"pass(word|wd)?|secret|token|authori[sz]ation|api[-_]?key|cookie", re.I)


def redact(value: Any) -> Any:
    """A copy of value with the contents of sensitive keys replaced by ***, at any depth."""
    if isinstance(value, dict):
        return {
            key: MASK
            if isinstance(key, str) and SENSITIVE_KEY.search(key) and item not in (None, "")
            else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact(item) for item in value]
    return value
