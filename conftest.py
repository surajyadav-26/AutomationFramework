"""Root pytest configuration: CLI options, browser context defaults, allure environment."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.reporting.allure_helpers import write_environment_properties
from core.settings import LOCALE, TIMEZONE, VIEWPORT, get_settings


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """One log file per xdist worker so parallel workers do not overwrite each other."""
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker:
        config.option.log_file = f"reports/logs/{worker}.log"


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
