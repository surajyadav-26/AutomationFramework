"""Root pytest configuration: CLI options, browser context defaults, allure environment."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.reporting.allure_helpers import write_environment_properties
from core.reporting.allure_report import generate_and_open
from core.reporting.log_files import daily_log_path, purge_old_logs
from core.settings import LOCALE, TIMEZONE, VIEWPORT, MissingSettingError, get_settings


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Apply .env driven logging, trace and video settings."""
    try:
        settings = get_settings()
    except MissingSettingError as error:
        raise pytest.UsageError(str(error)) from None
    # one daily file shared by ui, api, visual and every xdist worker
    config.option.log_file = str(daily_log_path())
    config.option.log_file_mode = "a"
    # explicit --tracing/--video on the command line win over .env
    if config.getoption("tracing") == "off":
        config.option.tracing = settings.trace_mode
    if config.getoption("video") == "off":
        config.option.video = settings.video_mode
    if not hasattr(config, "workerinput"):  # controller only
        purge_old_logs(settings.log_retention_days)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-baselines",
        action="store_true",
        default=False,
        help="write visual baselines for this OS/browser/viewport instead of comparing",
    )


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    """Fixed, deterministic rendering context for every browser test."""
    return {
        **browser_context_args,
        "viewport": dict(VIEWPORT),
        "locale": LOCALE,
        "timezone_id": TIMEZONE,
        "reduced_motion": "reduce",
    }


def _browser_name(config: pytest.Config) -> str:
    return (config.getoption("browser") or ["chromium"])[0]


def pytest_sessionfinish(session: pytest.Session) -> None:
    config = session.config
    if hasattr(config, "workerinput"):  # xdist worker; the controller writes the file
        return
    results_dir = config.getoption("allure_report_dir", None)
    if not results_dir:
        return
    settings = get_settings()
    write_environment_properties(
        Path(results_dir),
        {
            "env": settings.env,
            "app_url": settings.app_url,
            "api_url": settings.api_url,
            "browser": _browser_name(config),
        },
    )
    if settings.allure_auto_open and session.testscollected and not config.getoption("collectonly"):
        message = generate_and_open(
            Path(results_dir), Path(results_dir).parent / "allure-report", settings.allure_theme
        )
        print(f"\n{message}")
