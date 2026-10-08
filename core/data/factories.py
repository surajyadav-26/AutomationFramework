"""Test data: user lookup by role and unique value generators."""

from __future__ import annotations

import json
import uuid
from functools import lru_cache

from core.settings import ROOT


@lru_cache(maxsize=1)
def _users() -> dict[str, str]:
    return json.loads((ROOT / "test_data" / "users.json").read_text(encoding="utf-8"))


def username_for(role: str) -> str:
    users = _users()
    if role not in users:
        raise KeyError(f"unknown user role '{role}'; known: {sorted(users)}")
    return users[role]


def unique(prefix: str = "qa") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def random_password() -> str:
    """A password that cannot match any real account."""
    return unique("bad")
