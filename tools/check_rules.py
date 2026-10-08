"""Fail on selectors, URLs or raw HTTP in step files, duplicate step text, untagged features.

Usage: python tools/check_rules.py [root]   (root defaults to the repository root)
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

STEP_DECORATORS = {"given", "when", "then", "step"}
FORBIDDEN = {
    "selector": re.compile(
        r"data-test|\.locator\(|get_by_|\bxpath\b|\bcss=|querySelector|[\"'][#.][\w-]+[\"']"
    ),
    "URL": re.compile(r"https?://"),
    "raw HTTP": re.compile(r"\brequests\b|\bhttpx\b|\burllib\b|http\.client|\bsession\.(get|post)"),
}
SUITE_TAGS = {"@ui", "@api", "@visual"}


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


def check_steps(root: Path) -> list[str]:
    errors = []
    seen: dict[tuple[str, str], str] = {}
    for path in sorted((root / "steps").rglob("*.py")):
        rel = path.relative_to(root)
        source = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(source.splitlines(), 1):
            code = line.split("#", 1)[0]
            if code.lstrip().startswith(("import ", "from ")) and "requests" not in code:
                continue
            for label, pattern in FORBIDDEN.items():
                if pattern.search(code):
                    errors.append(f"{rel}:{lineno}: {label} in step file: {line.strip()}")
        suite = rel.parts[1] if len(rel.parts) > 2 else "shared"
        for text, lineno in step_texts(ast.parse(source)):
            key = (suite, text)
            if key in seen:
                errors.append(
                    f"{rel}:{lineno}: duplicate step text '{text}' (first at {seen[key]})"
                )
            else:
                seen[key] = f"{rel}:{lineno}"
    return errors


def check_features(root: Path) -> list[str]:
    errors = []
    for path in sorted((root / "features").rglob("*.feature")):
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
        tags = set(lines[0].split()) if lines and lines[0].startswith("@") else set()
        if not tags & SUITE_TAGS:
            errors.append(f"{path.relative_to(root)}: first line must tag @ui, @api or @visual")
    return errors


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parent.parent
    errors = check_steps(root) + check_features(root)
    for error in errors:
        print(error)
    print(f"check_rules: {'FAILED' if errors else 'ok'} ({len(errors)} problem(s))")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
