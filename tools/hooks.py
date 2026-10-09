"""Git hooks that run the framework rules before a commit and before a push.

Usage:
    python tools/hooks.py install      write .git/hooks/pre-commit and pre-push (bootstrap does it)
    python tools/hooks.py uninstall    remove the hooks this tool wrote (never anyone else's)
    python tools/hooks.py pre-commit   what the commit hook runs (fast: staged files + the rules)
    python tools/hooks.py pre-push     what the push hook runs (everything `make check` runs)

The pre-commit hook stops a commit that breaks the structure, tags or secrets rules, that has style
errors in the staged Python files, or that stages a local secret file (.env, .env.<name>). The
pre-push hook adds the architecture rules, mypy and the framework fingerprint. Skipping them with
--no-verify is possible, but CI runs the same checks, so it only moves the failure to the PR.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

MARKER = "# framework-hook"
HOOKS = ("pre-commit", "pre-push")
Runner = Callable[[list[str], Path], tuple[int, str]]


def run_command(command: list[str], cwd: Path) -> tuple[int, str]:
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return done.returncode, (done.stdout + done.stderr).strip()


def python(*args: str) -> list[str]:
    return [sys.executable, *args]


def lint_imports() -> list[str]:
    found = shutil.which("lint-imports")
    return (
        [found]
        if found
        else python("-c", "from importlinter.cli import lint_imports_command as c; c()")
    )


def hook_script(name: str) -> str:
    return (
        "#!/bin/sh\n"
        f"{MARKER}: runs the framework rules ({name}); written by tools/hooks.py\n"
        f'exec "${{PYTHON:-python}}" tools/hooks.py {name}\n'
    )


def staged_files(root: Path, runner: Runner = run_command) -> list[str]:
    code, output = runner(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"], root)
    return [line for line in output.splitlines() if line.strip()] if code == 0 else []


def secret_files(names: list[str]) -> list[str]:
    """Local secret files must never be committed: .env and .env.<name>, but not .env.example."""
    return [n for n in names if Path(n).name.startswith(".env") and Path(n).name != ".env.example"]


def report(label: str, code: int, output: str) -> bool:
    print(f"  {label:<34} {'ok' if code == 0 else 'FAILED'}")
    if code != 0 and output:
        print("\n".join("    " + line for line in output.splitlines()[-25:]))
    return code == 0


def pre_commit(root: Path, runner: Runner = run_command) -> int:
    print("pre-commit: checking the staged changes")
    names = staged_files(root, runner)
    results = []
    leaked = secret_files(names)
    results.append(report("no local secret files staged", 1 if leaked else 0, ", ".join(leaked)))
    py_files = [n for n in names if n.endswith(".py")]
    if py_files:
        results.append(
            report(
                "ruff check (staged files)", *runner(python("-m", "ruff", "check", *py_files), root)
            )
        )
        results.append(
            report(
                "ruff format (staged files)",
                *runner(python("-m", "ruff", "format", "--check", *py_files), root),
            )
        )
    results.append(report("repository rules", *runner(python("tools/check_rules.py"), root)))
    return 0 if all(results) else 1


def pre_push(root: Path, runner: Runner = run_command) -> int:
    print("pre-push: running the framework gates")
    checks = [
        ("ruff check", python("-m", "ruff", "check", ".")),
        ("ruff format", python("-m", "ruff", "format", "--check", ".")),
        ("architecture (lint-imports)", lint_imports()),
        ("mypy", python("-m", "mypy")),
        ("repository rules", python("tools/check_rules.py")),
        ("framework fingerprint", python("tools/fingerprint.py")),
    ]
    results = [report(label, *runner(command, root)) for label, command in checks]
    return 0 if all(results) else 1


def hooks_dir(root: Path) -> Path | None:
    git = root / ".git"
    return git / "hooks" if git.is_dir() else None


def install(root: Path, force: bool = False) -> list[str]:
    """Write the hooks. Returns one message per hook. Never overwrites someone else's hook."""
    folder = hooks_dir(root)
    if folder is None:
        return ["not a git repository (no .git folder): hooks were not installed"]
    folder.mkdir(parents=True, exist_ok=True)
    messages = []
    for name in HOOKS:
        target = folder / name
        if target.exists() and MARKER not in target.read_text(encoding="utf-8") and not force:
            messages.append(f"{name}: a different hook already exists, left alone (use --force)")
            continue
        target.write_text(hook_script(name), encoding="utf-8", newline="\n")
        target.chmod(0o755)
        messages.append(f"{name}: installed")
    return messages


def uninstall(root: Path) -> list[str]:
    folder = hooks_dir(root)
    if folder is None:
        return ["not a git repository: nothing to remove"]
    messages = []
    for name in HOOKS:
        target = folder / name
        if target.exists() and MARKER in target.read_text(encoding="utf-8"):
            target.unlink()
            messages.append(f"{name}: removed")
    return messages or ["no hooks of this tool were installed"]


def main(argv: list[str], root: Path | None = None, runner: Runner = run_command) -> int:
    root = root or Path(__file__).resolve().parent.parent
    command = argv[0] if argv else ""
    if command == "install":
        for message in install(root, force="--force" in argv):
            print(message)
        return 0
    if command == "uninstall":
        for message in uninstall(root):
            print(message)
        return 0
    if command == "pre-commit":
        return pre_commit(root, runner)
    if command == "pre-push":
        return pre_push(root, runner)
    print(__doc__)
    return 2


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    sys.exit(main(sys.argv[1:]))
