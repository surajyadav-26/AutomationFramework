"""Accessibility scan with axe-core (via axe-playwright-python)."""

from __future__ import annotations

from axe_playwright_python.sync_playwright import Axe

from core.reporting.allure_helpers import attach_json
from core.settings import IMPACTS

# WCAG 2.0/2.1/2.2 level A and AA rules, plus axe's own best-practice rules when asked for.
WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
BEST_PRACTICE_TAG = "best-practice"


def scan(page, include_best_practices: bool = False) -> list[dict]:
    """Run axe on the current page and return its violations (all impacts).

    Best-practice violations are mostly moderate or minor, so they show up in the report without
    failing a test at the default A11Y_FAIL_IMPACT.
    """
    tags = WCAG_TAGS + [BEST_PRACTICE_TAG] if include_best_practices else WCAG_TAGS
    result = Axe().run(page, options={"runOnly": {"type": "tag", "values": tags}})
    violations = result.response["violations"]
    attach_json(violations, f"Accessibility violations ({len(violations)})")
    return violations


def blocking(violations: list[dict], fail_impact: str) -> list[dict]:
    """Violations whose impact is at or above fail_impact."""
    threshold = IMPACTS.index(fail_impact)
    return [v for v in violations if IMPACTS.index(v.get("impact") or "minor") >= threshold]


def describe(violations: list[dict]) -> str:
    return "; ".join(
        f"{v['id']} ({v['impact']}, {len(v['nodes'])} element(s)): {v['help']}" for v in violations
    )
