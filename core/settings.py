"""Environment-driven settings: URLs from config/<TEST_ENV>.env, secrets from the env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
VIEWPORT = {"width": 1280, "height": 720}
TIMEZONE = "UTC"
LOCALE = "en-US"


class MissingSettingError(RuntimeError):
    pass


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise MissingSettingError(f"{name} is not set (see .env.example)")
    return value


@dataclass(frozen=True)
class Settings:
    env: str
    app_url: str
    api_url: str

    @property
    def app_password(self) -> str:
        return _require("APP_PASSWORD")

    @property
    def api_password(self) -> str:
        return _require("API_PASSWORD")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(ROOT / ".env")  # local secrets; never overrides real environment variables
    env = os.getenv("TEST_ENV", "qa")
    env_file = ROOT / "config" / f"{env}.env"
    if not env_file.exists():
        raise MissingSettingError(f"unknown TEST_ENV '{env}': {env_file} not found")
    load_dotenv(env_file)
    return Settings(env=env, app_url=_require("APP_URL"), api_url=_require("API_URL"))
