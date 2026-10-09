"""Prove that this copy of the framework is the same framework as everywhere else.

The framework-owned files (core/, tools/, tests_framework/, the suite fixtures, the pytest plugin
setup, the rule configuration in pyproject.toml, the dependency pins, the CI setup action) are
hashed into framework.manifest.json, which is committed. Project-owned files (features, the steps
and pages of an area, config, test_data, docs, tags) are not part of it, so adding tests never
changes it.

Usage:
    python tools/fingerprint.py            check this copy against the manifest (1 if different)
    python tools/fingerprint.py --update   write the manifest (after an intended framework change)
    python tools/fingerprint.py --show     print the fingerprint

After copying the framework to another system, run the check: "identical" means the same code, the
same rules and the same dependency pins. CI runs it too, so changing the framework is always a
visible, deliberate commit (change it, run --update, commit both).
"""

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path

MANIFEST = "framework.manifest.json"
# Files that belong to the framework (glob patterns, relative to the repository root).
INCLUDE = (
    "core/**/*.py",
    "tools/**/*.py",
    "tests_framework/**/*.py",
    "tests_framework/pytest.ini",
    "conftest.py",
    "steps/conftest.py",
    "steps/*/conftest.py",  # suite-level fixtures; an area's own conftest.py is project code
    "shared/__init__.py",
    "shared/browser_fixtures.py",
    ".github/actions/setup/action.yml",
    ".github/workflows/mutation.yml",
    "requirements.in",
    "requirements.lock",
    ".python-version",
    ".gitattributes",
)
CONFIG_ENTRY = "pyproject.toml#rules"
# pyproject tables that define the rules and tools. The list of tags (markers) is project data.
CONFIG_TABLES = ("ruff", "mypy", "coverage", "importlinter")


def normalised(data: bytes) -> bytes:
    """Same bytes on every OS: Windows checkouts may use CRLF line endings."""
    return data.replace(b"\r\n", b"\n")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def framework_files(root: Path) -> list[str]:
    found: set[str] = set()
    for pattern in INCLUDE:
        for path in root.glob(pattern):
            if path.is_file() and "__pycache__" not in path.parts:
                found.add(path.relative_to(root).as_posix())
    return sorted(found)


def rules_config(root: Path) -> dict:
    """The parts of pyproject.toml that define the framework's rules (not the project's tags)."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return {}
    tool = tomllib.loads(pyproject.read_text(encoding="utf-8")).get("tool", {})
    config = {name: tool[name] for name in CONFIG_TABLES if name in tool}
    pytest_options = dict(tool.get("pytest", {}).get("ini_options", {}))
    pytest_options.pop("markers", None)
    config["pytest"] = pytest_options
    return config


def collect(root: Path) -> dict[str, str]:
    """path -> sha256 for every framework file, plus the rule configuration."""
    entries = {
        path: sha256(normalised((root / path).read_bytes())) for path in framework_files(root)
    }
    entries[CONFIG_ENTRY] = sha256(json.dumps(rules_config(root), sort_keys=True).encode())
    return entries


def fingerprint(entries: dict[str, str]) -> str:
    """One hash for the whole framework."""
    text = "\n".join(f"{path}:{digest}" for path, digest in sorted(entries.items()))
    return sha256(text.encode())


def write_manifest(root: Path) -> dict[str, str]:
    entries = collect(root)
    manifest = {"fingerprint": fingerprint(entries), "files": entries}
    (root / MANIFEST).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return entries


def compare(root: Path) -> list[str]:
    """Differences between this copy and the committed manifest (empty = identical)."""
    path = root / MANIFEST
    if not path.exists():
        return [f"{MANIFEST} is missing (create it with: python tools/fingerprint.py --update)"]
    recorded: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))["files"]
    current = collect(root)
    problems = []
    for name in sorted(set(recorded) | set(current)):
        if name not in current:
            problems.append(f"missing: {name}")
        elif name not in recorded:
            problems.append(f"new framework file not in the manifest: {name}")
        elif recorded[name] != current[name]:
            what = "rule configuration in pyproject.toml" if name == CONFIG_ENTRY else name
            problems.append(f"changed: {what}")
    return problems


def short(entries: dict[str, str]) -> str:
    return fingerprint(entries)[:12]


def main(argv: list[str], root: Path | None = None) -> int:
    root = root or Path(__file__).resolve().parent.parent
    if "--update" in argv:
        entries = write_manifest(root)
        print(f"{MANIFEST} written: {len(entries)} entries, fingerprint {short(entries)}")
        return 0
    if "--show" in argv:
        print(fingerprint(collect(root)))
        return 0
    problems = compare(root)
    for problem in problems:
        print(problem)
    if problems:
        print(
            f"fingerprint: this copy differs from the manifest ({len(problems)} difference(s)).\n"
            "If the framework change is intended, run: python tools/fingerprint.py --update"
        )
        return 1
    entries = collect(root)
    print(f"fingerprint: identical to the manifest ({len(entries)} entries, {short(entries)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
