"""Markdown summary of an Allure results folder, for the GitHub Actions job summary.

Usage: python tools/ci_summary.py [results_dir]   (default: reports/allure-results)
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

STATUSES = ("passed", "failed", "broken", "skipped")


def load_results(results_dir: Path) -> list[dict]:
    results = []
    for path in sorted(results_dir.glob("*-result.json")):
        try:
            results.append(json.loads(path.read_text(encoding="utf-8")))
        except ValueError:
            continue  # a half-written file must not break the summary
    return results


def group_name(result: dict) -> str:
    labels = {label["name"]: label["value"] for label in result.get("labels", [])}
    return " / ".join(labels[key] for key in ("parentSuite", "suite", "subSuite") if key in labels)


def summarize(results_dir: Path) -> str:
    results = load_results(results_dir)
    if not results:
        return "### Test results\n\nNo Allure results were found.\n"
    totals = Counter(result.get("status", "unknown") for result in results)
    groups: dict[str, Counter] = defaultdict(Counter)
    for result in results:
        groups[group_name(result) or "(no suite)"][result.get("status", "unknown")] += 1

    lines = ["### Test results", ""]
    lines.append(
        f"**{len(results)} tests**: "
        + ", ".join(f"{totals[status]} {status}" for status in STATUSES if totals[status])
    )
    lines += ["", "| Suite | Passed | Failed | Broken | Skipped |", "|---|---:|---:|---:|---:|"]
    for name in sorted(groups):
        counts = groups[name]
        lines.append(f"| {name} | " + " | ".join(str(counts[s]) for s in STATUSES) + " |")
    failing = [r for r in results if r.get("status") in ("failed", "broken")]
    if failing:
        lines += ["", "#### Failures", ""]
        for result in failing:
            message = (result.get("statusDetails", {}).get("message") or "").strip().splitlines()
            lines.append(
                f"- **{group_name(result)}**: {result.get('name')}"
                + (f" - `{message[0][:160]}`" if message else "")
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    results_dir = Path(argv[1]) if len(argv) > 1 else Path("reports/allure-results")
    sys.stdout.write(summarize(results_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
