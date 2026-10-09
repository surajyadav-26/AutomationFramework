"""Root pytest configuration: command line options and plugin registration only.

The behaviour lives in two plugins: core.browser.plugin (browser context, test id attribute) and
core.reporting.plugin (settings applied to the run, areas, Allure grouping, attachments, report).
"""

from __future__ import annotations

import pytest

pytest_plugins = ["core.browser.plugin", "core.reporting.plugin"]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-baselines",
        action="store_true",
        default=False,
        help="write visual baselines for this OS/browser/viewport instead of comparing",
    )
    parser.addoption(
        "--area",
        action="append",
        default=[],
        metavar="NAME",
        help="run only the tests of this feature area, across all suites (repeatable)",
    )
