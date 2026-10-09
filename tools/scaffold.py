"""Create the files for a new feature area or page component, already wired and passing every gate.

Usage:
    python tools/scaffold.py area <name> [--suites ui,api,visual,accessibility] [--dry-run]
    python tools/scaffold.py component <name> [--dry-run]

`area cart --suites ui,api` creates, for the area "cart":
    features/<suite>/cart/cart.feature          feature tagged with its suite, one wiring scenario
    steps/<suite>/cart/                         __init__.py, conftest.py, test_cart_steps.py
    pages/cart/cart_page.py                     page object            (browser suites)
    shared/cart_fixtures.py                     the cart_page fixture  (browser suites)
    clients/cart/cart_client.py                 API client             (api suite)
Nothing existing is overwritten: if any target file exists the command stops before writing.
After scaffolding, add scenarios to the feature file, then write the matching steps and pages.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Same values as core/areas.py (a self-test keeps them equal; no core on this script's path)
SUITES = ("ui", "api", "visual", "accessibility")
BROWSER_SUITES = ("ui", "visual", "accessibility")
RESERVED = {*SUITES, "smoke", "shared", "components"}
DEFAULT_SUITES = ("ui", "api")


def is_valid_name(name: str) -> bool:
    return (
        name.isidentifier()
        and name == name.lower()
        and not name.startswith("_")
        and name not in RESERVED
    )


def words(name: str) -> tuple[str, str]:
    """order_history -> ('Order History', 'OrderHistory')."""
    parts = name.split("_")
    return " ".join(p.capitalize() for p in parts), "".join(p.capitalize() for p in parts)


FEATURE = """@{suite}
Feature: {title}
  Describe what the {title_lower} area does for the user, then add real scenarios below and
  delete the wiring scenario (pytest-bdd needs at least one scenario per feature file).

  Scenario: The {title_lower} area is wired up
    Given the {area} {thing} is available
"""
STEPS = '''"""Step definitions for features/{suite}/{area}/{area}.feature."""

from pytest_bdd import given, scenarios

scenarios("{suite}/{area}/{area}.feature")


@given("the {area} {thing} is available")
def _{area}_{kind}_is_available({fixture}):
    """Wiring check from tools/scaffold.py: replace it with the area's real steps."""
    assert {check}
'''
BROWSER_CONFTEST = '''"""Fixtures of the {area} area ({suite} suite)."""

from shared.{area}_fixtures import {area}_page  # noqa: F401
'''
API_CONFTEST = '''"""Fixtures of the {area} area (API suite)."""

from __future__ import annotations

import pytest

from clients.{area}.{area}_client import {cls}Client
from core.api.http_client import HttpClient
from core.settings import Settings


@pytest.fixture
def {area}_client(api_base_url: str, settings: Settings) -> {cls}Client:
    return {cls}Client(HttpClient(api_base_url, timeout=settings.api_timeout))
'''
SHARED_FIXTURES = '''"""Page fixture of the {area} area, used by its browser-suite steps."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from core.settings import Settings
from pages.{area}.{area}_page import {cls}Page


@pytest.fixture
def {area}_page(page: Page, settings: Settings) -> {cls}Page:
    return {cls}Page(page, settings.app_url)
'''
PAGE = '''"""{title} page."""

from __future__ import annotations

from core.browser.base_page import BasePage


class {cls}Page(BasePage):
    path = "/"  # the page's path under APP_URL: replace "/" with the real one

    def expect_loaded(self) -> None:
        """Wait until the page is really shown. Add its heading or key element here."""
        self.log.info("expect the {area} page loaded")
        self.expect_url_contains(self.path)
'''
CLIENT = '''"""Client of the {title_lower} endpoints."""

from __future__ import annotations

from core.api.http_client import HttpClient


class {cls}Client:
    def __init__(self, http: HttpClient):
        self.http = http
'''
COMPONENT = '''"""The {title} component."""

from __future__ import annotations

from playwright.sync_api import Page

from core.browser.base_component import BaseComponent


class {cls}(BaseComponent):
    def __init__(self, page: Page):
        # the root element of the widget; this assumes its data-test attribute is "{name}"
        super().__init__(page.get_by_test_id("{name}"))
'''


def plan_area(area: str, suites: tuple[str, ...]) -> dict[str, str]:
    """Relative path -> file content for a new area."""
    title, cls = words(area)
    values = {"area": area, "title": title, "title_lower": title.lower(), "cls": cls}
    files: dict[str, str] = {}
    for suite in suites:
        values["suite"] = suite
        if suite in BROWSER_SUITES:
            values |= {
                "thing": "page object", "kind": "page", "fixture": f"{area}_page",
                "check": f'{area}_page.path.startswith("/")',
            }  # fmt: skip
        else:
            values |= {
                "thing": "client", "kind": "client", "fixture": f"{area}_client",
                "check": f"{area}_client.http.base_url",
            }  # fmt: skip
        base = f"steps/{suite}/{area}"
        files[f"features/{suite}/{area}/{area}.feature"] = FEATURE.format(**values)
        files[f"{base}/__init__.py"] = ""
        files[f"{base}/test_{area}_steps.py"] = STEPS.format(**values)
        template = BROWSER_CONFTEST if suite in BROWSER_SUITES else API_CONFTEST
        files[f"{base}/conftest.py"] = template.format(**values)
    if any(s in BROWSER_SUITES for s in suites):
        files[f"pages/{area}/__init__.py"] = ""
        files[f"pages/{area}/{area}_page.py"] = PAGE.format(**values)
        files[f"shared/{area}_fixtures.py"] = SHARED_FIXTURES.format(**values)
    if "api" in suites:
        files[f"clients/{area}/__init__.py"] = ""
        files[f"clients/{area}/{area}_client.py"] = CLIENT.format(**values)
    return files


def plan_component(name: str) -> dict[str, str]:
    title, cls = words(name)
    return {f"pages/components/{name}.py": COMPONENT.format(name=name, title=title, cls=cls)}


def existing(root: Path, plan: dict[str, str]) -> list[str]:
    return sorted(path for path in plan if (root / path).exists())


def write(root: Path, plan: dict[str, str]) -> None:
    for path, content in plan.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")


def parse_suites(text: str) -> tuple[str, ...]:
    chosen = tuple(dict.fromkeys(s.strip() for s in text.split(",") if s.strip()))
    unknown = [s for s in chosen if s not in SUITES]
    if unknown or not chosen:
        raise ValueError(f"--suites must list some of {list(SUITES)}; got {unknown or text!r}")
    return chosen


def usage() -> str:
    return (__doc__ or "").split("\n\n")[1]


def main(argv: list[str], root: Path | None = None, out=sys.stdout) -> int:
    root = root or Path(__file__).resolve().parent.parent
    args = argv[1:]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    suites_text = ",".join(DEFAULT_SUITES)
    if "--suites" in args:
        index = args.index("--suites")
        if index + 1 >= len(args):
            print("--suites needs a value", file=out)
            return 2
        suites_text = args[index + 1]
        del args[index : index + 2]
    if len(args) != 2 or args[0] not in ("area", "component"):
        print(usage(), file=out)
        return 2
    kind, name = args
    if not is_valid_name(name):
        print(
            f"'{name}' is not a valid {kind} name: use a lower-case identifier such as "
            "'order_history' that is not a reserved word "
            f"({', '.join(sorted(RESERVED))}).",
            file=out,
        )
        return 2
    try:
        plan = (
            plan_area(name, parse_suites(suites_text)) if kind == "area" else plan_component(name)
        )
    except ValueError as error:
        print(error, file=out)
        return 2
    clashes = existing(root, plan)
    if clashes:
        print(f"Nothing written: these files already exist: {', '.join(clashes)}", file=out)
        return 1
    if dry_run:
        print("Would create:", file=out)
        for path in sorted(plan):
            print(f"  {path}", file=out)
        return 0
    write(root, plan)
    print(f"Created {len(plan)} file(s) for the {kind} '{name}':", file=out)
    for path in sorted(plan):
        print(f"  {path}", file=out)
    print("Next:", file=out)
    if kind == "area":
        print(f"  1. add real scenarios to features/<suite>/{name}/{name}.feature", file=out)
        print(
            "     and delete the wiring scenario (it only proves the files are connected)", file=out
        )
        print("  2. write the steps in steps/<suite>/<area>/test_*_steps.py", file=out)
        print(
            "  3. fill in the page object or client; list the new steps in docs/VOCABULARY.md",
            file=out,
        )
        print("  4. add the area to .github/CODEOWNERS; run `make check`", file=out)
    else:
        print(f"  1. set the root locator in pages/components/{name}.py, add its parts", file=out)
        print("  2. use it from a page object (self.header = Header(page) style)", file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
