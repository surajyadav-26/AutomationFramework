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


TRACE_MODES = ("off", "on", "retain-on-failure")
VIDEO_MODES = ("off", "on", "retain-on-failure")


def _choice(name: str, default: str, allowed: tuple[str, ...]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in allowed:
        raise MissingSettingError(f"{name}='{value}' is invalid; use one of {allowed}")
    return value


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        raise MissingSettingError(f"{name}='{raw}' must be an integer") from None


@dataclass(frozen=True)
class Settings:
    env: str
    app_url: str
    api_url: str
    log_retention_days: int = 7  # 0 keeps logs forever
    trace_mode: str = "retain-on-failure"
    video_mode: str = "retain-on-failure"

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
    return Settings(
        env=env,
        app_url=_require("APP_URL"),
        api_url=_require("API_URL"),
        log_retention_days=_int("LOG_RETENTION_DAYS", 7),
        trace_mode=_choice("TRACE_MODE", "retain-on-failure", TRACE_MODES),
        video_mode=_choice("VIDEO_MODE", "retain-on-failure", VIDEO_MODES),
    )
