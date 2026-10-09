"""Set up this machine for the framework and prove that it is right. One command, safe to repeat.

Usage (python tools/bootstrap.py ...):
    (no option)       install, set up .env and the git hooks, then verify
    --check           verify only: installs nothing, changes nothing
    --browsers all    also install firefox and webkit (default: chromium); --browsers none: skip
    --no-hooks        do not install the git hooks
    --no-install      do not run pip or install browsers
    --full            also run the whole `make check` and the framework self-tests
    --with-deps       let Playwright install system libraries (Linux, needs root)

What it does, in order:
  1. checks the Python version against .python-version
  2. installs the pinned dependencies (requirements.lock) and the Playwright browsers
  3. creates .env from .env.example if there is none (it never overwrites yours)
  4. installs the git hooks that run the framework rules before every commit and push
  5. verifies: packages match the lock file, the framework is identical to its manifest
     (tools/fingerprint.py), the repository rules pass (tools/check_rules.py)
Copying the framework to another system: copy the repository, run this once, read the last lines.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

Runner = Callable[[list[str], Path], tuple[int, str]]
FIRST_STEPS = (
    "Next: put the real URLs in config/qa.env, set APP_PASSWORD and API_PASSWORD in .env, then "
    "`python tools/scaffold.py area <name>`."
)


def run_command(command: list[str], cwd: Path) -> tuple[int, str]:
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return done.returncode, (done.stdout + done.stderr).strip()


def python(*args: str) -> list[str]:
    return [sys.executable, *args]


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def step(self, label: str, ok: bool, detail: str = "") -> bool:
        print(f"  [{'ok' if ok else 'FAILED'}] {label}" + (f" - {detail}" if detail else ""))
        if not ok:
            self.failures.append(label)
        return ok


def wanted_python(root: Path) -> str | None:
    path = root / ".python-version"
    return (
        ".".join(path.read_text(encoding="utf-8").strip().split(".")[:2]) if path.exists() else None
    )


def check_python(root: Path, report: Report, version: tuple[int, int] | None = None) -> bool:
    wanted = wanted_python(root)
    major, minor = version or (sys.version_info[0], sys.version_info[1])
    if wanted is None:
        return report.step(
            "python version", True, f"{major}.{minor} (no .python-version to compare)"
        )
    return report.step(
        "python version", wanted == f"{major}.{minor}", f"{major}.{minor}, wanted {wanted}"
    )


def ensure_env_file(root: Path, report: Report) -> None:
    env, example = root / ".env", root / ".env.example"
    if env.exists():
        report.step(".env", True, "already there, left as it is")
    elif example.exists():
        shutil.copyfile(example, env)
        report.step(".env", True, "created from .env.example: set APP_PASSWORD and API_PASSWORD")
    else:
        report.step(".env", False, ".env.example is missing")


def install_everything(root: Path, report: Report, runner: Runner, args: list[str]) -> None:
    code, output = runner(python("-m", "pip", "install", "-r", "requirements.lock"), root)
    report.step("dependencies (requirements.lock)", code == 0, "" if code == 0 else output[-300:])
    browsers = args[args.index("--browsers") + 1] if "--browsers" in args else "chromium"
    if browsers != "none":
        names = ["chromium", "firefox", "webkit"] if browsers == "all" else [browsers]
        install = python("-m", "playwright", "install")
        if "--with-deps" in args:
            install.append("--with-deps")
        code, output = runner([*install, *names], root)
        report.step(
            f"playwright browsers ({', '.join(names)})",
            code == 0,
            "" if code == 0 else output[-300:],
        )
    else:
        report.step("playwright browsers", True, "skipped (--browsers none)")


def verify(root: Path, report: Report, runner: Runner, full: bool) -> None:
    checks = [
        ("packages match requirements.lock", python("tools/check_env.py")),
        ("framework identical to its manifest", python("tools/fingerprint.py")),
        ("repository rules", python("tools/check_rules.py")),
    ]
    if full:
        checks += [
            ("ruff check", python("-m", "ruff", "check", ".")),
            ("ruff format", python("-m", "ruff", "format", "--check", ".")),
            ("mypy", python("-m", "mypy")),
            ("framework self-tests", python("-m", "pytest", "-c", "tests_framework/pytest.ini",
                                            "tests_framework", "-q", "--tb=short")),
        ]  # fmt: skip
    for label, command in checks:
        code, output = runner(command, root)
        last = output.splitlines()[-1] if output else ""
        report.step(label, code == 0, last if code != 0 else "")
        if code != 0 and output:
            print("\n".join("      " + line for line in output.splitlines()[-12:]))


def main(argv: list[str], root: Path | None = None, runner: Runner = run_command) -> int:
    root = root or Path(__file__).resolve().parent.parent
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    check_only = "--check" in argv
    report = Report()
    print(f"bootstrap {'(verify only)' if check_only else ''} in {root}".replace("  ", " "))
    if not check_python(root, report):
        print("Install the Python version in .python-version and run this again.")
        return 1
    if not check_only:
        if "--no-install" not in argv:
            install_everything(root, report, runner, argv)
        ensure_env_file(root, report)
        if "--no-hooks" not in argv:
            code, output = runner(python("tools/hooks.py", "install"), root)
            report.step("git hooks", code == 0, output.splitlines()[0] if output else "")
    verify(root, report, runner, full="--full" in argv)
    if report.failures:
        print(f"bootstrap: FAILED ({len(report.failures)}): {', '.join(report.failures)}")
        return 1
    print("bootstrap: ok. " + ("" if check_only else FIRST_STEPS))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
