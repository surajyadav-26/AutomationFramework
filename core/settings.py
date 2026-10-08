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
ALLURE_THEMES = ("dark", "light")
API_MODES = ("live", "stub")
IMPACTS = ("minor", "moderate", "serious", "critical")  # ascending severity


def _choice(name: str, default: str, allowed: tuple[str, ...]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in allowed:
        raise MissingSettingError(f"{name}='{value}' is invalid; use one of {allowed}")
    return value


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value not in ("true", "false", "1", "0", "yes", "no"):
        raise MissingSettingError(f"{name}='{raw}' must be true or false")
    return value in ("true", "1", "yes")


def _float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError:
        raise MissingSettingError(f"{name}='{raw}' must be a number") from None
    if value < minimum:
        raise MissingSettingError(f"{name}={value} must be at least {minimum}")
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
    allure_auto_open: bool = True  # generate and open the report after the run (never in CI)
    allure_theme: str = "dark"
    a11y_fail_impact: str = "serious"  # lowest impact that fails an accessibility test
    api_timeout: float = 15.0  # seconds per API request
    api_mode: str = "live"  # live: the real service; stub: in-process fake for offline runs
    rerun_count: int = 1  # reruns of a test after an infrastructure error (0 disables)
    rerun_delay: float = 1.0  # seconds between reruns
    visual_ignore_antialiasing: bool = False  # ignore 1-2px wide diffs (anti-aliasing noise)

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
        allure_auto_open=_bool("ALLURE_AUTO_OPEN", True) and not os.getenv("CI"),
        allure_theme=_choice("ALLURE_THEME", "dark", ALLURE_THEMES),
        a11y_fail_impact=_choice("A11Y_FAIL_IMPACT", "serious", IMPACTS),
        api_timeout=_float("API_TIMEOUT", 15.0, minimum=0.1),
        api_mode=_choice("API_MODE", "live", API_MODES),
        rerun_count=_int("RERUN_COUNT", 1),
        rerun_delay=_float("RERUN_DELAY", 1.0),
        visual_ignore_antialiasing=_bool("VISUAL_IGNORE_ANTIALIASING", False),
    )
