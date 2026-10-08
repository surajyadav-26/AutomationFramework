"""Accessibility scan with axe-core (via axe-playwright-python)."""

from __future__ import annotations

from axe_playwright_python.sync_playwright import Axe

from core.reporting.allure_helpers import attach_json
from core.settings import IMPACTS

# WCAG 2.0/2.1/2.2 level A and AA rules; best-practice rules are reported by axe but not scanned.
WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]


def scan(page) -> list[dict]:
    """Run axe on the current page and return its violations (all impacts)."""
    result = Axe().run(page, options={"runOnly": {"type": "tag", "values": WCAG_TAGS}})
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
