"""Shared fixtures and hooks for all suites."""

from __future__ import annotations

import logging

import pytest

from core.data.cleanup import Cleanup
from core.reporting.allure_helpers import attach_png
from core.settings import Settings, get_settings

log = logging.getLogger("hooks")


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(autouse=True)
def cleanup():
    """Registry of teardown callbacks; they run even when the test failed."""
    registry = Cleanup()
    yield registry
    failures = registry.run_all()
    assert not failures, f"cleanup callbacks failed: {failures}"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    page = item.funcargs.get("page")
    if page is None:
        return
    try:
        attach_png(page.screenshot(full_page=True), "Failure screenshot")
    except Exception:
        log.exception("could not capture failure screenshot")
