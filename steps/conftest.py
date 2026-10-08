"""Shared fixtures and hooks for all suites."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from core.data.cleanup import Cleanup
from core.reporting.allure_helpers import attach_file, attach_png, suite_marks
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
        callspec = getattr(item, "callspec", None)
        browser = callspec.params.get("browser_name") if callspec else None
        if browser and len(config.getoption("browser") or []) > 1:
            area = f"{area} ({browser})"  # cross-browser run: one group per browser
        for mark in suite_marks(markers, area, smoke_run):
            item.add_marker(mark)


def _fixture(item: pytest.Item, name: str) -> Any:
    """Value of a fixture for a running test (pytest-bdd resolves fixtures dynamically)."""
    if not isinstance(item, pytest.Function):
        raise LookupError(f"{item.nodeid} is not a test function")
    return item._request.getfixturevalue(name)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    if not any(item.get_closest_marker(m) for m in ("ui", "visual", "accessibility")):
        return
    try:
        page = _fixture(item, "page")
        attach_png(page.screenshot(full_page=True), "Failure screenshot")
    except Exception:
        log.exception("could not capture failure screenshot")


ARTIFACTS = (
    ("trace.zip", "Playwright trace (python -m playwright show-trace <file>)", "application/zip"),
    ("video.webm", "Playwright video", "video/webm"),
)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item: pytest.Item):
    """Attach the Playwright trace and video (kept per TRACE_MODE / VIDEO_MODE) to the report."""
    folder = None
    if (
        item.get_closest_marker("ui")
        or item.get_closest_marker("visual")
        or item.get_closest_marker("accessibility")
    ):
        try:  # pytest-playwright's per-test output folder; the fixture is still alive here
            folder = Path(_fixture(item, "output_path"))
        except Exception:
            log.exception("could not find the Playwright output folder")
    yield
    if folder is None:
        return
    for file_name, title, mime_type in ARTIFACTS:
        if (folder / file_name).exists():
            attach_file(folder / file_name, title, mime_type, file_name.rsplit(".", 1)[1])
