"""Test the tests: break the framework code on purpose and check the self-tests notice.

Each mutant is one small, deliberate bug (a flipped comparison, a disabled check...). For every mutant
the self-tests run; if they still pass, the bug "survived" and a test is missing. The source file is
always restored afterwards, even if the run is interrupted.

Usage:
    python tools/mutation_check.py              run all mutants (a few minutes)
    python tools/mutation_check.py --list       list them
    python tools/mutation_check.py comparator   only mutants whose label or file contains the text
Exit code 1 if any mutant survives or no longer applies (stale after a refactor).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF_TEST_COMMAND = [
    sys.executable, "-m", "pytest", "-c", "tests_framework/pytest.ini", "tests_framework",
    "-q", "-x", "-n", "4", "-p", "no:cacheprovider",
]  # fmt: skip


@dataclass(frozen=True)
class Mutant:
    file: str
    old: str
    new: str
    label: str


@dataclass(frozen=True)
class Result:
    mutant: Mutant
    status: str  # killed | survived | stale


MUTANTS = [
    Mutant("core/visual/comparator.py", "v > tolerance", "v > tolerance + 40", "comparator: tolerance too loose"),
    Mutant("core/visual/comparator.py", "ok = ratio <= max_ratio", "ok = True", "comparator: everything matches"),
    Mutant("core/visual/comparator.py", "changed = changed.filter(ImageFilter.MinFilter(3))", "pass", "comparator: anti-aliasing option does nothing"),
    Mutant("core/visual/baseline_store.py", '"Darwin": "macos"', '"Darwin": "mac"', "baseline_store: wrong macOS folder"),
    Mutant("core/reporting/log_files.py", "st_mtime < cutoff", "st_mtime > cutoff", "log retention: deletes the new files"),
    Mutant("core/reporting/log_files.py", "if retention_days <= 0", "if retention_days < 0", "log retention: 0 no longer keeps everything"),
    Mutant("core/data/cleanup.py", "self._callbacks.pop()", "self._callbacks.pop(0)", "cleanup: runs in the wrong order"),
    Mutant("core/data/cleanup.py", "failures.append(description)", "pass", "cleanup: hides failing callbacks"),
    Mutant("core/settings.py", ' and not os.getenv("CI")', "", "settings: report opens in CI"),
    Mutant("core/settings.py", 'if not value.startswith(("http://", "https://")) or " " in value:', "if False:", "settings: URLs not validated"),
    Mutant("core/settings.py", 'return value.rstrip("/")', "return value", "settings: trailing slash kept"),
    Mutant("core/settings.py", 'load_dotenv(ROOT / f".env.{env}")', "pass", "settings: per-environment secrets ignored"),
    Mutant("core/api/validator.py", "if errors:", "if False:", "validator: schema violations pass"),
    Mutant("core/api/redaction.py", "SENSITIVE_KEY.search(key)", "None", "redaction: nothing is masked"),
    Mutant("core/api/redaction.py", "|secret|token|authori", "|secret|authori", "redaction: tokens are not masked"),
    Mutant("core/api/http_client.py", 'kwargs.setdefault("timeout", self.timeout)', "pass", "http client: no timeout"),
    Mutant("core/api/stub_server.py", 'return self._send(400, {"message": "Invalid credentials"})', 'return self._send(200, {"message": "Invalid credentials"})', "stub server: bad login accepted"),
    Mutant("core/accessibility/axe_scanner.py", '.index(v.get("impact") or "minor") >= threshold', '.index(v.get("impact") or "minor") > threshold', "axe: threshold impact not included"),
    Mutant("core/browser/base_page.py", "visibility: hidden", "display: none", "base page: hiding changes the layout"),
    Mutant("core/browser/base_page.py", 'self.page.evaluate("document.fonts.ready.then(() => true)")', "pass", "base page: does not wait for fonts"),
    Mutant("core/reporting/plugin.py", "if isinstance(mark, str | pytest.MarkDecorator):", "if False:", "plugin: suite grouping never applied"),
    Mutant("tools/check_rules.py", '"URL": re.compile(r"https?://"),', '"URL": re.compile(r"NEVERMATCH"),', "check_rules: URLs allowed in steps"),
    Mutant("tools/check_rules.py", 'if used and file_name[: -len(".png")] not in used.get(area, set()):', "if False:", "check_rules: orphan baselines allowed"),
    Mutant("tools/check_rules.py", "if SECRET_ASSIGNMENT.search(line):", "if False:", "check_rules: secret literals allowed"),
    Mutant("tools/ci_summary.py", 'in ("failed", "broken")]', 'in ("failed",)]', "ci_summary: broken tests not listed"),
    Mutant("tools/check_env.py", "elif have != wanted:", "elif False:", "check_env: version drift ignored"),
    Mutant("pyproject.toml", "--only-rerun=^(TimeoutError|ConnectTimeout|", "--only-rerun=^(TimeoutError|", "pyproject.toml: connect timeouts not retried"),
    Mutant("tools/check_rules.py", "if wanted not in called:", "if False:", "check_rules: steps need not call scenarios() for a feature"),
    Mutant("tools/check_rules.py", 'elif parts[0] == "pages" and len(parts) >= 2 and parts[1] not in (area, "components"):', "elif False:", "check_rules: steps may import another area's pages"),
    Mutant("tools/check_rules.py", "if tag not in registered", "if False", "check_rules: unregistered tags allowed"),
    Mutant("tools/check_rules.py", 'if folder_suite in SUITES and f"@{folder_suite}" not in tags:', "if False:", "check_rules: feature tag may differ from its folder"),
    Mutant("tools/check_rules.py", 'clashes.append("shared")', "pass", "check_rules: a suite may redefine a shared step"),
    Mutant("tools/check_rules.py", "if areas and area not in areas:", "if False:", "check_rules: baselines of unknown areas allowed"),
    Mutant("core/settings.py", "if env in PROTECTED_ENVS and not allow_prod:", "if False:", "settings: production runs without confirmation"),
    Mutant("core/data/factories.py", "if override.exists():", "if False:", "factories: per-environment users ignored"),
    Mutant("core/reporting/plugin.py", "if wanted and area not in wanted:", "if False:", "plugin: --area ignored"),
    Mutant("core/reporting/plugin.py", "item.add_marker(getattr(pytest.mark, area))", "pass", "plugin: tests get no area marker"),
    Mutant("core/reporting/plugin.py", "if unknown:", "if False:", "plugin: an unknown area is accepted"),
    Mutant("core/reporting/plugin.py", "config.option.reruns = settings.rerun_count", "pass", "plugin: RERUN_COUNT ignored"),
    Mutant("core/reporting/allure_helpers.py", "if smoke_run:", "if False:", "allure: smoke runs are not grouped under Smoke"),
    Mutant("core/areas.py", "return below[1]", "return below[0]", "areas: the suite is mistaken for the area"),
]  # fmt: skip


def apply_mutant(root: Path, mutant: Mutant) -> bytes | None:
    """Write the mutated file and return the original bytes, or None if the mutant is stale."""
    path = root / mutant.file
    original = path.read_bytes()
    text = original.decode("utf-8")
    if mutant.old not in text:
        return None
    path.write_bytes(text.replace(mutant.old, mutant.new, 1).encode("utf-8"))
    return original


def evaluate(root: Path, mutants: Iterable[Mutant], run_tests: Callable[[], bool]) -> list[Result]:
    """run_tests() returns True when the self-tests pass. Files are restored in every case."""
    if not run_tests():
        raise RuntimeError("the self-tests fail even without a mutation; fix them first")
    results = []
    for mutant in mutants:
        original = apply_mutant(root, mutant)
        if original is None:
            results.append(Result(mutant, "stale"))
            continue
        try:
            passed = run_tests()
        finally:
            (root / mutant.file).write_bytes(original)
        results.append(Result(mutant, "survived" if passed else "killed"))
    return results


def select(mutants: Iterable[Mutant], text: str | None) -> list[Mutant]:
    if not text:
        return list(mutants)
    return [m for m in mutants if text in m.label or text in m.file]


def default_runner() -> bool:  # pragma: no cover (starts the real self-tests)
    return subprocess.run(SELF_TEST_COMMAND, cwd=ROOT, capture_output=True).returncode == 0


def main(argv: list[str]) -> int:  # pragma: no cover (drives the real self-tests)
    args = argv[1:]
    chosen = select(MUTANTS, next((a for a in args if not a.startswith("--")), None))
    if "--list" in args:
        for mutant in chosen:
            print(f"{mutant.file}: {mutant.label}")
        return 0
    print(f"running the self-tests once without changes, then {len(chosen)} mutants ...")
    results = evaluate(ROOT, chosen, default_runner)
    for result in results:
        print(f"{result.status.upper():9} {result.mutant.label}  ({result.mutant.file})")
    bad = [r for r in results if r.status != "killed"]
    print(f"mutation_check: {len(results) - len(bad)} of {len(results)} killed")
    return 1 if bad else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
