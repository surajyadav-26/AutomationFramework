"""Doctor: does this Python environment match the lock files?

Checks (exit code 1 if any of the first three fails):
  1. the Python version matches .python-version (major.minor)
  2. every package pinned in requirements.lock / requirements-quality.lock is installed, same pin
  3. every direct dependency in requirements.in / requirements-quality.in is pinned in a lock file
  4. warns about installed packages known to clash with ours (allure-pytest)

Usage: python tools/check_env.py        (make doctor)
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable, Mapping
from importlib.metadata import distributions
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCKS = ("requirements.lock", "requirements-quality.lock")
DIRECT = ("requirements.in", "requirements-quality.in")
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==(\S+)")
CLASHES = {
    "allure-pytest": "clashes with allure-pytest-bdd (both register --alluredir); pytest.ini "
    "disables it with '-p no:allure_pytest', but uninstalling it is cleaner",
}


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_pins(text: str) -> dict[str, str]:
    """{normalised name: version} from the 'name==version' lines of a lock file."""
    pins = {}
    for line in text.splitlines():
        match = PIN.match(line.strip())
        if match:
            pins[normalise(match.group(1))] = match.group(2)
    return pins


def parse_direct(text: str) -> list[str]:
    """Normalised names from a requirements.in file (comments and options ignored)."""
    names = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            names.append(normalise(re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0]))
    return names


def python_problem(wanted: str, actual: tuple[int, int]) -> str | None:
    major_minor = ".".join(wanted.strip().split(".")[:2])
    if major_minor != f"{actual[0]}.{actual[1]}":
        return f"Python {actual[0]}.{actual[1]} is running, .python-version asks for {major_minor}"
    return None


def drift_problems(pins: Mapping[str, str], installed: Mapping[str, str]) -> list[str]:
    problems = []
    for name, wanted in sorted(pins.items()):
        have = installed.get(name)
        if have is None:
            problems.append(f"{name}=={wanted} is pinned but not installed")
        elif have != wanted:
            problems.append(f"{name}: lock pins {wanted}, installed {have}")
    return problems


def unpinned_direct(direct: Iterable[str], pins: Mapping[str, str]) -> list[str]:
    return [
        f"{name} is a direct dependency but is not pinned in a lock file"
        for name in direct
        if name not in pins
    ]


def installed_versions() -> dict[str, str]:
    found = {}
    for dist in distributions():
        name = dist.metadata["Name"]
        if name:
            found[normalise(name)] = dist.version
    return found


def main() -> int:
    problems: list[str] = []
    wanted_file = ROOT / ".python-version"
    if wanted_file.exists():
        problem = python_problem(wanted_file.read_text(encoding="utf-8"), sys.version_info[:2])
        if problem:
            problems.append(problem)

    pins: dict[str, str] = {}
    for lock in LOCKS:
        path = ROOT / lock
        if path.exists():
            pins.update(parse_pins(path.read_text(encoding="utf-8")))
    installed = installed_versions()
    problems += drift_problems(pins, installed)

    direct: list[str] = []
    for name in DIRECT:
        path = ROOT / name
        if path.exists():
            direct += parse_direct(path.read_text(encoding="utf-8"))
    problems += unpinned_direct(direct, pins)

    for name, why in CLASHES.items():
        if name in installed:
            print(f"warning: {name} {installed[name]} is installed: {why}")

    for problem in problems:
        print(problem)
    print(
        f"check_env: {'FAILED' if problems else 'ok'} "
        f"({len(pins)} pinned, {len(problems)} problem(s))"
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
