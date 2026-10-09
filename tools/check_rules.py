"""Repository rules that tools can enforce (run by `make check`, pre-push and CI).

Code rules
  - no selectors, URLs or raw HTTP in step files (steps/ and shared/); no duplicate step text
  - no XPath, positional or long CSS chains, or manual sleeps in pages, browser core and steps
Structure rules (one area name ties the folders together, see docs/CONTRIBUTING.md)
  - features/<suite>/<area>/<name>.feature is tagged with its suite, and has a step module in
    steps/<suite>/<area>/ that calls scenarios("<suite>/<area>/<name>.feature"), and a page folder
    (browser suites) or client folder (api) for the area
  - areas stay independent: steps, pages and clients of one area never import another area's
  - tags used in features are registered in pyproject.toml and documented in docs/TAGS.md
  - visual baselines are baselines/<os>/<browser>/<WxH>/<area>/<name>.png, none is orphaned, and
    windows/macos baselines are not committed
Secrets
  - no secret literal assigned in a committed file, and no known secret value in any of them

Usage: python tools/check_rules.py [root]   (root defaults to the repository root)
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

# --- vocabulary (core/areas.py has the same values; a self-test keeps them equal) ----------------
SUITES = ("ui", "api", "visual", "accessibility")
BROWSER_SUITES = ("ui", "visual", "accessibility")
RESERVED = {*SUITES, "smoke", "shared", "components"}
SUITE_TAGS = {f"@{suite}" for suite in SUITES}
STEP_ROOTS = ("steps", "shared")

# --- code rules ----------------------------------------------------------------------------------
STEP_DECORATORS = {"given", "when", "then", "step"}
FORBIDDEN = {
    "selector": re.compile(
        r"data-test|\.locator\(|get_by_|\bxpath\b|\bcss=|querySelector|[\"'][#.][\w-]+[\"']"
    ),
    "URL": re.compile(r"https?://"),
    "raw HTTP": re.compile(
        r"\b(import|from)\s+(requests|httpx|urllib)\b"
        r"|\brequests\.(get|post|put|patch|delete|request|Session)\b"
        r"|\bhttpx\.|\burllib\.|\bhttp\.client\b|\bsession\.(get|post)\b"
    ),
}
# Fragile locator styles and manual waits, banned in pages/, core/browser/, steps/ and shared/
FRAGILE = {
    "XPath locator": re.compile(r"xpath|[\"'](//|\(//)"),
    "positional selector": re.compile(r":nth-(child|of-type)|:first-child|:last-child"),
    "long child-combinator chain": re.compile(r">\s*[\w.#\[\]=\"'-]+\s*>\s*[\w.#\[\]=\"'-]+\s*>"),
    "manual sleep": re.compile(r"\btime\.sleep\(|\bwait_for_timeout\("),
}


def step_texts(tree: ast.AST) -> list[tuple[str, int]]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for deco in node.decorator_list:
            if not (
                isinstance(deco, ast.Call) and getattr(deco.func, "id", None) in STEP_DECORATORS
            ):
                continue
            if not deco.args:
                continue
            arg = deco.args[0]
            if isinstance(arg, ast.Call) and arg.args:  # parsers.parse("...") / parsers.re("...")
                arg = arg.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.append((re.sub(r"\{[^}]*\}", "{}", arg.value), deco.lineno))
    return found


def step_files(root: Path) -> list[Path]:
    return sorted(
        p for base in STEP_ROOTS if (root / base).exists() for p in (root / base).rglob("*.py")
    )


def suite_of(rel: Path) -> str:
    """steps/<suite>/<area>/x.py -> <suite>; shared/ and steps/conftest.py -> 'shared'."""
    if rel.parts[0] == "steps" and len(rel.parts) > 2:
        return rel.parts[1]
    return "shared"


def check_steps(root: Path) -> list[str]:
    errors = []
    seen: dict[tuple[str, str], str] = {}
    for path in step_files(root):
        rel = path.relative_to(root)
        source = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(source.splitlines(), 1):
            code = line.split("#", 1)[0]
            if code.lstrip().startswith(("import ", "from ")) and not FORBIDDEN["raw HTTP"].search(
                code
            ):
                continue
            for label, pattern in FORBIDDEN.items():
                if pattern.search(code):
                    errors.append(f"{rel}:{lineno}: {label} in step file: {line.strip()}")
        suite = suite_of(rel)
        for text, lineno in step_texts(ast.parse(source)):
            # a shared step is used by the browser suites, so it clashes with theirs too
            clashes = [suite]
            if suite == "shared":
                clashes += list(BROWSER_SUITES)
            elif suite in BROWSER_SUITES:
                clashes.append("shared")
            first = next((seen[(s, text)] for s in clashes if (s, text) in seen), None)
            if first:
                errors.append(f"{rel}:{lineno}: duplicate step text '{text}' (first at {first})")
            else:
                seen[(suite, text)] = f"{rel}:{lineno}"
    return errors


def check_locators(root: Path) -> list[str]:
    """No XPath, positional/long CSS chains or manual sleeps in pages, browser core and steps."""
    errors = []
    for folder in ("pages", "core/browser", "steps", "shared"):
        if not (root / folder).exists():
            continue
        for path in sorted((root / folder).rglob("*.py")):
            rel = path.relative_to(root)
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("#", 1)[0]
                for label, pattern in FRAGILE.items():
                    if pattern.search(code):
                        errors.append(f"{rel}:{lineno}: {label}: {line.strip()}")
    return errors


# --- features: tags ------------------------------------------------------------------------------
def check_features(root: Path) -> list[str]:
    errors = []
    for path in sorted((root / "features").rglob("*.feature")):
        rel = path.relative_to(root)
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        tags = set(lines[0].split()) if lines and lines[0].startswith("@") else set()
        if not tags & SUITE_TAGS:
            errors.append(f"{rel}: first line must tag @ui, @api, @visual, @accessibility")
            continue
        folder_suite = rel.parts[1] if len(rel.parts) > 1 else ""
        if folder_suite in SUITES and f"@{folder_suite}" not in tags:
            wrong = sorted(tags & SUITE_TAGS)
            errors.append(f"{rel}: lives in features/{folder_suite}/ but is tagged {wrong}")
    return errors


# --- structure: one area name ties the folders together ------------------------------------------
SCENARIOS_CALL = re.compile(r"""scenarios\(\s*["']([^"']+)["']""")


def is_valid_area_name(name: str) -> bool:
    return (
        name.isidentifier()
        and name == name.lower()
        and not name.startswith("_")
        and name not in RESERVED
    )


def known_areas(root: Path) -> set[str]:
    features = root / "features"
    if not features.exists():
        return set()
    return {p.name for p in features.glob("*/*") if p.is_dir() and not p.name.startswith("_")}


def check_structure(root: Path) -> list[str]:
    """features/<suite>/<area>/x.feature <-> steps/<suite>/<area>/ <-> pages/ or clients/<area>/."""
    errors: list[str] = []
    features = root / "features"
    if not features.exists():
        return errors
    for path in sorted(features.rglob("*.feature")):
        rel = path.relative_to(root)
        parts = rel.parts
        if len(parts) != 4:
            errors.append(f"{rel.as_posix()}: expected features/<suite>/<area>/<name>.feature")
            continue
        _, suite, area, file_name = parts
        if suite not in SUITES:
            errors.append(f"{rel.as_posix()}: '{suite}' is not a suite folder {list(SUITES)}")
            continue
        if not is_valid_area_name(area):
            errors.append(
                f"{rel.as_posix()}: '{area}' is not a valid area name "
                "(lower-case identifier, not a reserved word)"
            )
            continue
        steps_dir = root / "steps" / suite / area
        if not (steps_dir / "__init__.py").exists():
            errors.append(f"{rel.as_posix()}: missing steps/{suite}/{area}/ (with __init__.py)")
        else:
            wanted = f"{suite}/{area}/{file_name}"
            called = {
                called_path
                for module in steps_dir.glob("test_*.py")
                for called_path in SCENARIOS_CALL.findall(module.read_text(encoding="utf-8"))
            }
            if wanted not in called:
                errors.append(
                    f"{rel.as_posix()}: no step module in steps/{suite}/{area}/ "
                    f'calls scenarios("{wanted}")'
                )
        owner = "pages" if suite in BROWSER_SUITES else "clients"
        if not (root / owner / area / "__init__.py").exists():
            errors.append(f"{rel.as_posix()}: missing {owner}/{area}/ (with __init__.py)")
    errors += check_scenario_targets(root)
    return errors


def check_scenario_targets(root: Path) -> list[str]:
    """Every scenarios("...") call points at an existing feature of its own suite and area."""
    errors: list[str] = []
    steps = root / "steps"
    if not steps.exists():
        return errors
    for module in sorted(steps.glob("*/*/test_*.py")):
        rel = module.relative_to(root)
        _, suite, area, _file = rel.parts
        for target in SCENARIOS_CALL.findall(module.read_text(encoding="utf-8")):
            if not target.startswith(f"{suite}/{area}/"):
                errors.append(f"{rel.as_posix()}: scenarios('{target}') is outside {suite}/{area}/")
            elif not (root / "features" / target).exists():
                errors.append(f"{rel.as_posix()}: scenarios('{target}') points at a missing file")
    return errors


def imported_modules(path: Path) -> list[tuple[int, str]]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.lineno, node.module))
    return found


def check_area_independence(root: Path) -> list[str]:
    """An area never imports another area. Shared code goes in shared/, pages/components or core."""
    errors = []

    def report(rel: Path, lineno: int, module: str, why: str) -> None:
        errors.append(f"{rel.as_posix()}:{lineno}: imports {module}: {why}")

    for path in sorted((root / "steps").rglob("*.py")) if (root / "steps").exists() else []:
        rel = path.relative_to(root)
        if len(rel.parts) < 4:
            continue  # steps/conftest.py and the suite __init__ files
        _, suite, area = rel.parts[:3]
        for lineno, module in imported_modules(path):
            parts = module.split(".")
            if parts[0] == "steps" and len(parts) >= 3 and parts[1] in SUITES:
                if (parts[1], parts[2]) != (suite, area):
                    report(rel, lineno, module, "steps of another suite or area")
            elif parts[0] == "pages" and len(parts) >= 2 and parts[1] not in (area, "components"):
                report(rel, lineno, module, f"pages of another area (this is '{area}')")
            elif parts[0] == "clients" and len(parts) >= 2 and parts[1] != area:
                report(rel, lineno, module, f"clients of another area (this is '{area}')")
    for owner in ("pages", "clients"):
        if not (root / owner).exists():
            continue
        for path in sorted((root / owner).rglob("*.py")):
            rel = path.relative_to(root)
            if len(rel.parts) < 3:
                continue
            area = rel.parts[1]
            for lineno, module in imported_modules(path):
                parts = module.split(".")
                if parts[0] == owner and len(parts) >= 2 and parts[1] != area:
                    allowed = area != "components" and parts[1] == "components" and owner == "pages"
                    if not allowed:
                        report(rel, lineno, module, f"another area's {owner} (this is '{area}')")
    return errors


# --- tags ------------------------------------------------------------------------------------
def registered_markers(root: Path) -> set[str] | None:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return None
    config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    markers = config.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("markers", [])
    return {marker.split(":", 1)[0].strip() for marker in markers}


def check_tags(root: Path) -> list[str]:
    """Tags used in features are registered in pyproject.toml; registered tags are in TAGS.md."""
    registered = registered_markers(root)
    features = root / "features"
    if registered is None or not features.exists():
        return []
    used: dict[str, str] = {}
    for path in sorted(features.rglob("*.feature")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("@"):
                for tag in line.split():
                    if tag.startswith("@"):
                        used.setdefault(tag[1:], path.relative_to(root).as_posix())
    errors = [
        f"{where}: tag @{tag} is not a registered marker in pyproject.toml"
        for tag, where in sorted(used.items())
        if tag not in registered
    ]
    docs = root / "docs" / "TAGS.md"
    if not docs.exists():
        return errors + ["docs/TAGS.md is missing (it lists every tag)"]
    text = docs.read_text(encoding="utf-8")
    for tag in sorted(registered):  # an unregistered tag was already reported above
        if f"@{tag}" not in text:
            errors.append(f"docs/TAGS.md: tag @{tag} is not documented")
    return errors


# --- visual baselines ----------------------------------------------------------------------------
BASELINE_OSES = {"linux", "windows", "macos"}
BASELINE_BROWSERS = {"chromium", "firefox", "webkit"}
LOCAL_ONLY_OSES = ("windows", "macos")  # gitignored: rendering differs per machine
BASELINE_NAME_USE = re.compile(r"assert_matches_baseline\(\s*\"([a-z0-9_]+)\"")


def check_baselines(root: Path) -> list[str]:
    """Baselines are baselines/<os>/<browser>/<WxH>/<area>/<name>.png, the name is used by a visual
    step of that area, and no windows or macos baseline is committed."""
    folder = root / "baselines"
    if not folder.exists():
        return []
    used: dict[str, set[str]] = {}
    visual = root / "steps" / "visual"
    for path in visual.rglob("*.py") if visual.exists() else []:
        area = path.relative_to(visual).parts[0]
        used.setdefault(area, set()).update(
            BASELINE_NAME_USE.findall(path.read_text(encoding="utf-8"))
        )
    areas = known_areas(root)
    errors = []
    for path in sorted(folder.rglob("*.png")):
        parts = path.relative_to(folder).parts
        label = path.relative_to(root).as_posix()
        if len(parts) != 5:
            errors.append(f"{label}: expected baselines/<os>/<browser>/<WxH>/<area>/<name>.png")
            continue
        os_name, browser, size, area, file_name = parts
        if os_name not in BASELINE_OSES:
            errors.append(f"{label}: unknown OS folder '{os_name}'")
        if browser not in BASELINE_BROWSERS:
            errors.append(f"{label}: unknown browser folder '{browser}'")
        if not re.fullmatch(r"\d+x\d+", size):
            errors.append(f"{label}: viewport folder '{size}' is not <width>x<height>")
        if areas and area not in areas:
            errors.append(f"{label}: '{area}' is not an area (features/<suite>/{area}/ is missing)")
            continue
        if used and file_name[: -len(".png")] not in used.get(area, set()):
            errors.append(f"{label}: no visual step of area '{area}' checks this name (orphan)")
    errors += committed_local_baselines(root)
    return errors


def committed_local_baselines(root: Path) -> list[str]:
    """Windows and macOS baselines must stay local: rendering differs between machines."""
    if not (root / ".git").exists():
        return []
    try:
        listed = subprocess.run(
            ["git", "ls-files", "baselines"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return []
    return [
        f"{name}: local-only baseline is committed (baselines stay on the machine that made them)"
        for name in listed
        if name.split("/")[1:2] and name.split("/")[1] in LOCAL_ONLY_OSES
    ]


# --- secrets -------------------------------------------------------------------------------------
SECRET_ASSIGNMENT = re.compile(
    r"\b[A-Z0-9_]*(PASSWORD|SECRET|TOKEN|API_?KEY)[A-Z0-9_]*\s*[=:]\s*[\"']?"
    r"(?![\"'$<{\s]|$)(?![A-Za-z_.]+\()[^\s\"']{3,}"
)
SECRET_NAME = re.compile(r"[A-Z0-9_]*(PASSWORD|SECRET|TOKEN|API_?KEY)[A-Z0-9_]*")
SKIP_DIRS = {
    ".git", ".venv", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    ".import_linter_cache", "reports", "logs", "baselines", "htmlcov", "node_modules",
    "tests_framework",
}  # fmt: skip
MIN_SECRET_LENGTH = 4


def known_secret_values(root: Path) -> set[str]:
    """Values of *PASSWORD / *SECRET / *TOKEN settings in the local .env and the environment."""
    pairs: dict[str, str] = dict(os.environ)
    env_file = root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                pairs.setdefault(key.strip(), value.strip().strip("\"'"))
    return {
        value
        for key, value in pairs.items()
        if SECRET_NAME.fullmatch(key) and len(value) >= MIN_SECRET_LENGTH
    }


def check_secrets(root: Path) -> list[str]:
    """No secret literals assigned in committed files, and no known secret value in any of them."""
    errors = []
    secrets = known_secret_values(root)
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or SKIP_DIRS & set(relative.parts):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue  # local secret files, gitignored by design
        if path.stat().st_size > 1_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary file
        for lineno, line in enumerate(text.splitlines(), 1):
            if SECRET_ASSIGNMENT.search(line):
                errors.append(f"{relative}:{lineno}: secret assigned a literal value")
            for value in secrets:
                if value in line:
                    errors.append(f"{relative}:{lineno}: contains the value of a secret setting")
    return errors


CHECKS = (
    check_steps,
    check_locators,
    check_features,
    check_structure,
    check_area_independence,
    check_tags,
    check_baselines,
    check_secrets,
)


def run_all(root: Path) -> list[str]:
    return [error for check in CHECKS for error in check(root)]


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parent.parent
    errors = run_all(root)
    for error in errors:
        print(error)
    print(f"check_rules: {'FAILED' if errors else 'ok'} ({len(errors)} problem(s))")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
