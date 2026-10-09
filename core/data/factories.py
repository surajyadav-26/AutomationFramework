"""Test data: user lookup by role (per environment) and unique value generators."""

from __future__ import annotations

import json
import uuid
from functools import cache

from core.settings import ROOT, get_settings

TEST_DATA = ROOT / "test_data"


@cache
def _users(env: str) -> dict[str, str]:
    """test_data/users.json, overridden per role by test_data/users.<env>.json when it exists."""
    users: dict[str, str] = json.loads((TEST_DATA / "users.json").read_text(encoding="utf-8"))
    override = TEST_DATA / f"users.{env}.json"
    if override.exists():
        users = {**users, **json.loads(override.read_text(encoding="utf-8"))}
    return users


def username_for(role: str) -> str:
    users = _users(get_settings().env)
    if role not in users:
        raise KeyError(f"unknown user role '{role}'; known: {sorted(users)}")
    return users[role]


def unique(prefix: str = "qa") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def random_password() -> str:
    """A password that cannot match any real account."""
    return unique("bad")
