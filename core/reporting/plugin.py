"""pytest plugin: everything that decides how a run is configured, grouped and reported.

Registered by the root conftest.py (pytest_plugins). It:
- applies the .env settings (daily log file, reruns, trace and video modes, log retention),
- adds the area marker to every test and implements --area,
- groups tests in the Allure Suites tab (UI / Auth / Login; Smoke / UI / Auth on a smoke run),
- attaches a failure screenshot and the Playwright trace and video,
- writes environment.properties, opens the Allure report and lists retried tests.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from core.areas import area_of, discover_areas
from core.reporting.allure_helpers import (
    attach_file,
    attach_png,
    suite_marks,
    write_environment_properties,
)
from core.reporting.allure_report import generate_and_open
from core.reporting.log_files import daily_log_path, purge_old_logs
from core.settings import MissingSettingError, get_settings

log = logging.getLogger("hooks")
BROWSER_SUITES = ("ui", "visual", "accessibility")
ARTIFACTS = (
    ("trace.zip", "Playwright trace (python -m playwright show-trace <file>)", "application/zip"),
    ("video.webm", "Playwright video", "video/webm"),
)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Apply .env driven logging, rerun, trace and video settings and register the areas."""
    try:
        settings = get_settings()
    except MissingSettingError as error:
        raise pytest.UsageError(str(error)) from None
    areas = discover_areas(config.rootpath)
    for area in areas:
        config.addinivalue_line("markers", f"{area}: tests of the {area} area (run with --area)")
    unknown = sorted(set(config.getoption("area", None) or []) - set(areas))
    if unknown:
        raise pytest.UsageError(f"unknown area {unknown}; known areas: {areas}")
    # one daily file shared by ui, api, visual, accessibility and every xdist worker
    config.option.log_file = str(daily_log_path())
    config.option.log_file_mode = "a"
    # explicit --reruns/--reruns-delay on the command line win over .env
    if config.option.reruns is None:
        config.option.reruns = settings.rerun_count
    if config.option.reruns_delay is None:
        config.option.reruns_delay = settings.rerun_delay
    # explicit --tracing/--video on the command line win over .env
    if config.getoption("tracing") == "off":
        config.option.tracing = settings.trace_mode
    if config.getoption("video") == "off":
        config.option.video = settings.video_mode
    if not hasattr(config, "workerinput"):  # controller only
        purge_old_logs(settings.log_retention_days)


def _label(item: pytest.Item) -> str:
    """steps/<suite>/<area>/test_<name>_steps.py -> '<Name>'."""
    return item.path.stem.removeprefix("test_").removesuffix("_steps").replace("_", " ").title()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Tag every test with its area, apply --area, and group the tests for the Allure report."""
    wanted = set(config.getoption("area", None) or [])
    expression = config.getoption("markexpr") or ""
    smoke_run = "smoke" in expression and "not smoke" not in expression
    multi_browser = len(config.getoption("browser") or []) > 1
    kept, dropped = [], []
    for item in items:
        area = area_of(item.path)
        if wanted and area not in wanted:
            dropped.append(item)
            continue
        kept.append(item)
        if area:
            item.add_marker(getattr(pytest.mark, area))
        markers = {m.name for m in item.iter_markers()}
        name = _label(item)
        shown_area = area.replace("_", " ").title() if area else None
        callspec = getattr(item, "callspec", None)
        browser = callspec.params.get("browser_name") if callspec else None
        if browser and multi_browser:  # cross-browser run: one group per browser
            if shown_area:
                shown_area = f"{shown_area} ({browser})"
            else:
                name = f"{name} ({browser})"
        for mark in suite_marks(markers, shown_area, name, smoke_run):
            # without an active Allure plugin (no --alluredir) the decorators are inert placeholders
            if isinstance(mark, str | pytest.MarkDecorator):
                item.add_marker(mark)
    if dropped:
        items[:] = kept
        config.hook.pytest_deselected(items=dropped)


def _fixture(item: pytest.Item, name: str) -> Any:
    """Value of a fixture for a running test (pytest-bdd resolves fixtures dynamically)."""
    if not isinstance(item, pytest.Function):
        raise LookupError(f"{item.nodeid} is not a test function")
    return item._request.getfixturevalue(name)


def _is_browser_test(item: pytest.Item) -> bool:
    return any(item.get_closest_marker(suite) for suite in BROWSER_SUITES)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed or not _is_browser_test(item):
        return
    try:
        page = _fixture(item, "page")
        attach_png(page.screenshot(full_page=True), "Failure screenshot")
    except Exception:
        log.exception("could not capture failure screenshot")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item: pytest.Item):
    """Attach the Playwright trace and video (kept per TRACE_MODE / VIDEO_MODE) to the report."""
    folder = None
    if get_settings().attach_trace_and_video and _is_browser_test(item):
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
            "browser": ", ".join(config.getoption("browser") or ["chromium"]),
        },
    )
    if settings.allure_auto_open and session.testscollected and not config.getoption("collectonly"):
        message = generate_and_open(
            Path(results_dir), Path(results_dir).parent / "allure-report", settings.allure_theme
        )
        print(f"\n{message}")


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """List tests that were retried after an infrastructure error (they may be flaky)."""
    retried = sorted({report.nodeid for report in terminalreporter.stats.get("rerun", [])})
    if retried:
        terminalreporter.section("retried after infrastructure errors")
        for nodeid in retried:
            terminalreporter.line(nodeid)
