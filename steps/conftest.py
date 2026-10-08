"""Shared fixtures and hooks for all suites."""

from __future__ import annotations

import logging

import pytest

from core.data.cleanup import Cleanup
from core.reporting.allure_helpers import attach_png, suite_marks
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


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Separate ui / api / visual in the report; a -m smoke run nests them under 'Smoke'."""
    expression = config.getoption("markexpr") or ""
    smoke_run = "smoke" in expression and "not smoke" not in expression
    for item in items:
        markers = {m.name for m in item.iter_markers()}
        # steps/<suite>/test_<name>_steps.py -> "<Name>"
        area = item.path.stem.removeprefix("test_").removesuffix("_steps").replace("_", " ").title()
        browser = getattr(item, "callspec", None) and item.callspec.params.get("browser_name")
        if browser and len(config.getoption("browser") or []) > 1:
            area = f"{area} ({browser})"  # cross-browser run: one group per browser
        for mark in suite_marks(markers, area, smoke_run):
            item.add_marker(mark)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    if not (item.get_closest_marker("ui") or item.get_closest_marker("visual")):
        return
    try:
        # pytest-bdd resolves fixtures dynamically, so `page` is not in item.funcargs.
        page = item._request.getfixturevalue("page")
        attach_png(page.screenshot(full_page=True), "Failure screenshot")
    except Exception:
        log.exception("could not capture failure screenshot")
