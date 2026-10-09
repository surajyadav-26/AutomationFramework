"""Copying the framework to another system: fingerprint, git hooks and bootstrap.

fingerprint.py proves a copy is identical, hooks.py makes the rules run before commits and pushes,
bootstrap.py sets a machine up and verifies it. The runner-based tests use a fake runner (no pip, no
browsers); the last tests run real git commits against the real hook scripts.
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fingerprint = load("fingerprint")
hooks = load("hooks")
bootstrap = load("bootstrap")


def write(root, relative, text="x = 1\n"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


PYPROJECT = """
[tool.ruff]
line-length = 100
[tool.importlinter]
root_packages = ["steps", "core"]
[tool.pytest.ini_options]
markers = ["ui: ui tests"]
addopts = ["-ra"]
"""


@pytest.fixture
def framework(tmp_path):
    """A tiny project with one file of every kind the fingerprint knows about."""
    for relative in (
        "core/a.py", "core/sub/b.py", "tools/t.py", "tests_framework/test_x.py", "conftest.py",
        "steps/conftest.py", "steps/ui/conftest.py", "shared/__init__.py",
        "shared/browser_fixtures.py", "requirements.in", "requirements.lock", ".python-version",
        ".gitattributes", ".github/actions/setup/action.yml", ".github/workflows/mutation.yml",
    ):  # fmt: skip
        write(tmp_path, relative)
    write(tmp_path, "tests_framework/pytest.ini", "[pytest]\n")
    write(tmp_path, "pyproject.toml", PYPROJECT)
    return tmp_path


# --- fingerprint -----------------------------------------------------------------------------


def test_every_framework_file_and_the_rule_configuration_is_in_the_fingerprint(framework):
    entries = fingerprint.collect(framework)
    assert "core/sub/b.py" in entries
    assert "steps/ui/conftest.py" in entries
    assert "tests_framework/pytest.ini" in entries
    assert fingerprint.CONFIG_ENTRY in entries
    assert len(entries) == 17


def test_project_files_are_not_part_of_the_fingerprint(framework):
    before = fingerprint.fingerprint(fingerprint.collect(framework))
    write(framework, "features/ui/cart/cart.feature", "@ui\nFeature: x\n")
    write(framework, "steps/ui/cart/conftest.py")  # an area's own conftest is project code
    write(framework, "steps/ui/cart/test_cart_steps.py")
    write(framework, "pages/cart/cart_page.py")
    write(framework, "clients/cart/cart_client.py")
    write(framework, "shared/cart_fixtures.py")
    write(framework, "config/qa.env", "APP_URL=https://x\n")
    write(framework, "docs/TAGS.md", "tags")
    write(framework, "ci.yml")
    assert fingerprint.fingerprint(fingerprint.collect(framework)) == before


def test_adding_a_tag_does_not_change_it_but_changing_a_rule_does(framework):
    before = fingerprint.fingerprint(fingerprint.collect(framework))
    write(
        framework, "pyproject.toml", PYPROJECT.replace('["ui: ui tests"]', '["ui: a", "slow: b"]')
    )
    assert fingerprint.fingerprint(fingerprint.collect(framework)) == before
    write(framework, "pyproject.toml", PYPROJECT.replace("line-length = 100", "line-length = 120"))
    assert fingerprint.fingerprint(fingerprint.collect(framework)) != before


def test_line_endings_do_not_matter(framework):
    (framework / "core" / "a.py").write_bytes(b"x = 1\n")
    lf = fingerprint.collect(framework)["core/a.py"]
    (framework / "core" / "a.py").write_bytes(b"x = 1\r\n")
    assert fingerprint.collect(framework)["core/a.py"] == lf


def test_caches_are_ignored(framework):
    before = fingerprint.collect(framework)
    write(framework, "core/__pycache__/a.cpython-312.pyc")
    assert fingerprint.collect(framework) == before


def test_a_fresh_manifest_matches_and_every_kind_of_change_is_reported(framework):
    fingerprint.write_manifest(framework)
    assert fingerprint.compare(framework) == []
    write(framework, "core/a.py", "x = 2\n")  # changed
    (framework / "tools" / "t.py").unlink()  # missing
    write(framework, "core/brand_new.py")  # new
    write(framework, "pyproject.toml", PYPROJECT.replace("100", "99"))  # rules changed
    assert fingerprint.compare(framework) == [  # sorted by file name
        "changed: core/a.py",
        "new framework file not in the manifest: core/brand_new.py",
        "changed: rule configuration in pyproject.toml",
        "missing: tools/t.py",
    ]


def test_a_missing_manifest_is_reported_with_the_fix(framework):
    assert "framework.manifest.json is missing" in fingerprint.compare(framework)[0]


def test_the_manifest_records_one_fingerprint_for_all_files(framework):
    entries = fingerprint.write_manifest(framework)
    recorded = json.loads((framework / fingerprint.MANIFEST).read_text(encoding="utf-8"))
    assert recorded["fingerprint"] == fingerprint.fingerprint(entries)
    assert recorded["files"] == entries


def test_the_command_line_checks_updates_and_shows(framework, capsys):
    assert fingerprint.main([], framework) == 1  # no manifest yet
    assert fingerprint.main(["--update"], framework) == 0
    assert "17 entries" in capsys.readouterr().out
    assert fingerprint.main([], framework) == 0
    assert "identical to the manifest" in capsys.readouterr().out
    write(framework, "core/a.py", "x = 3\n")
    assert fingerprint.main([], framework) == 1
    assert "changed: core/a.py" in capsys.readouterr().out
    assert fingerprint.main(["--show"], framework) == 0
    assert len(capsys.readouterr().out.strip()) == 64


def test_this_copy_of_the_framework_is_identical_to_its_committed_manifest():
    """The gate CI runs: change the framework, run `python tools/fingerprint.py --update`."""
    assert fingerprint.compare(ROOT) == []


# --- git hooks: scripts and install -----------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def test_hook_scripts_call_this_tool_through_a_shell_script(repo):
    script = hooks.hook_script("pre-commit")
    assert script.startswith("#!/bin/sh\n")
    assert hooks.MARKER in script
    assert "tools/hooks.py pre-commit" in script


def test_install_writes_both_hooks_and_is_repeatable(repo):
    assert hooks.install(repo) == ["pre-commit: installed", "pre-push: installed"]
    assert hooks.install(repo) == ["pre-commit: installed", "pre-push: installed"]
    for name in hooks.HOOKS:
        assert hooks.MARKER in (repo / ".git" / "hooks" / name).read_text(encoding="utf-8")


def test_a_hook_somebody_else_wrote_is_never_overwritten_without_force(repo):
    foreign = repo / ".git" / "hooks" / "pre-commit"
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    messages = hooks.install(repo)
    assert "pre-commit: a different hook already exists" in messages[0]
    assert foreign.read_text(encoding="utf-8") == "#!/bin/sh\necho mine\n"
    assert hooks.install(repo, force=True)[0] == "pre-commit: installed"


def test_outside_a_git_repository_nothing_is_installed(tmp_path):
    assert "not a git repository" in hooks.install(tmp_path)[0]
    assert "not a git repository" in hooks.uninstall(tmp_path)[0]


def test_uninstall_removes_only_the_hooks_this_tool_wrote(repo):
    hooks.install(repo)
    foreign = repo / ".git" / "hooks" / "pre-push"
    foreign.write_text("#!/bin/sh\necho mine\n", encoding="utf-8")
    assert hooks.uninstall(repo) == ["pre-commit: removed"]
    assert foreign.exists()
    assert hooks.uninstall(repo) == ["no hooks of this tool were installed"]


# --- git hooks: what they run -----------------------------------------------------------------


class FakeRunner:
    """Records commands and answers 'git diff' with a staged file list."""

    def __init__(self, staged=(), failing=()):
        self.staged, self.failing, self.commands = list(staged), list(failing), []

    def __call__(self, command, cwd):
        self.commands.append(command)
        if command[:2] == ["git", "diff"]:
            return 0, "\n".join(self.staged)
        joined = " ".join(command)
        return (1, "boom") if any(word in joined for word in self.failing) else (0, "")


def ran(runner, word):
    return [c for c in runner.commands if word in " ".join(c)]


@pytest.mark.parametrize(
    ("names", "leaked"),
    [
        ([".env"], [".env"]),
        (["config/.env.prod", ".env.stage"], ["config/.env.prod", ".env.stage"]),
        ([".env.example", "core/a.py", "envelope.py"], []),
    ],
)
def test_local_secret_files_are_recognised_but_the_example_file_is_not(names, leaked):
    assert hooks.secret_files(names) == leaked


def test_the_commit_hook_checks_only_the_staged_python_files_and_the_rules(capsys):
    runner = FakeRunner(staged=["core/a.py", "README.md", "tools/t.py"])
    assert hooks.pre_commit(Path("."), runner) == 0
    ruff = ran(runner, "ruff")
    assert len(ruff) == 2
    assert all(c[-2:] == ["core/a.py", "tools/t.py"] for c in ruff)
    assert ran(runner, "check_rules")
    assert "repository rules" in capsys.readouterr().out


def test_the_commit_hook_skips_ruff_when_no_python_file_is_staged():
    runner = FakeRunner(staged=["README.md"])
    assert hooks.pre_commit(Path("."), runner) == 0
    assert not ran(runner, "ruff")
    assert ran(runner, "check_rules")


@pytest.mark.parametrize("failing", ["ruff check", "ruff format", "check_rules"])
def test_the_commit_hook_fails_when_any_check_fails(failing, capsys):
    runner = FakeRunner(staged=["core/a.py"], failing=[failing])
    assert hooks.pre_commit(Path("."), runner) == 1
    assert "FAILED" in capsys.readouterr().out


def test_the_commit_hook_refuses_a_staged_secret_file(capsys):
    runner = FakeRunner(staged=[".env", "core/a.py"])
    assert hooks.pre_commit(Path("."), runner) == 1
    assert "no local secret files staged" in capsys.readouterr().out


def test_the_push_hook_runs_every_gate_and_fails_if_one_does():
    runner = FakeRunner()
    assert hooks.pre_push(Path("."), runner) == 0
    joined = [" ".join(c) for c in runner.commands]
    for word in ("ruff check", "ruff format", "mypy", "check_rules", "fingerprint"):
        assert any(word in line for line in joined), word
    assert any("importlinter" in line or "lint-imports" in line for line in joined)
    assert hooks.pre_push(Path("."), FakeRunner(failing=["fingerprint"])) == 1


def test_the_hook_command_line(repo, capsys):
    assert hooks.main(["install"], repo) == 0
    assert hooks.main(["uninstall"], repo) == 0
    assert hooks.main(["pre-commit"], repo, FakeRunner(staged=[])) == 0
    assert hooks.main(["pre-push"], repo, FakeRunner()) == 0
    assert hooks.main([], repo) == 2


# --- git hooks: real commits ----------------------------------------------------------------------


def git(repo, *args, check=True):
    env = {**os.environ, "PYTHON": sys.executable}
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo, env=env, capture_output=True, text=True, check=check,
    )  # fmt: skip


@pytest.fixture
def hooked_repo(repo):
    for name in ("hooks", "check_rules", "fingerprint"):
        write(repo, f"tools/{name}.py", (ROOT / "tools" / f"{name}.py").read_text(encoding="utf-8"))
    assert hooks.install(repo)
    return repo


def test_a_real_commit_with_a_wrongly_tagged_feature_is_blocked(hooked_repo):
    write(hooked_repo, "features/api/cart/cart.feature", "@ui\nFeature: x\n")
    git(hooked_repo, "add", "features")
    result = git(hooked_repo, "commit", "-m", "add feature", check=False)
    assert result.returncode != 0
    assert "pre-commit" in result.stdout + result.stderr
    assert "repository rules" in result.stdout + result.stderr
    assert "FAILED" in result.stdout + result.stderr


def test_a_real_commit_of_a_secret_file_is_blocked(hooked_repo):
    write(hooked_repo, ".env", "APP_PASSWORD=whatever\n")
    git(hooked_repo, "add", "-f", ".env")
    result = git(hooked_repo, "commit", "-m", "oops", check=False)
    assert result.returncode != 0
    assert "no local secret files staged" in result.stdout + result.stderr


def test_a_real_commit_that_follows_the_rules_goes_through(hooked_repo):
    write(hooked_repo, "notes.md", "# notes\n")
    git(hooked_repo, "add", "notes.md")
    result = git(hooked_repo, "commit", "-m", "notes", check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pre-commit" in result.stdout + result.stderr


# --- bootstrap -----------------------------------------------------------------------------------


class Recorder:
    def __init__(self, failing=()):
        self.commands, self.failing = [], list(failing)

    def __call__(self, command, cwd):
        self.commands.append(command)
        joined = " ".join(command)
        return (1, "it broke") if any(word in joined for word in self.failing) else (0, "fine")


@pytest.fixture
def machine(tmp_path, monkeypatch):
    version = ".".join(str(n) for n in sys.version_info[:2])
    write(tmp_path, ".python-version", version + "\n")
    write(tmp_path, ".env.example", "APP_PASSWORD=\n")
    return tmp_path


def words(recorder):
    return [" ".join(c[1:]) for c in recorder.commands]


def test_a_full_bootstrap_installs_prepares_hooks_and_verifies(machine, capsys):
    recorder = Recorder()
    assert bootstrap.main([], machine, recorder) == 0
    steps = words(recorder)
    assert steps[0] == "-m pip install -r requirements.lock"
    assert steps[1] == "-m playwright install chromium"
    assert steps[2] == "tools/hooks.py install"
    assert steps[3:] == ["tools/check_env.py", "tools/fingerprint.py", "tools/check_rules.py"]
    assert (machine / ".env").read_text() == "APP_PASSWORD=\n"
    out = capsys.readouterr().out
    assert "bootstrap: ok." in out
    assert "scaffold.py area" in out


def test_check_mode_changes_nothing_and_only_verifies(machine, capsys):
    recorder = Recorder()
    assert bootstrap.main(["--check"], machine, recorder) == 0
    assert words(recorder) == ["tools/check_env.py", "tools/fingerprint.py", "tools/check_rules.py"]
    assert not (machine / ".env").exists()
    assert "bootstrap: ok. " in capsys.readouterr().out


def test_an_existing_env_file_is_never_overwritten(machine):
    (machine / ".env").write_text("APP_PASSWORD=mine\n")
    bootstrap.main([], machine, Recorder())
    assert (machine / ".env").read_text() == "APP_PASSWORD=mine\n"


@pytest.mark.parametrize(
    ("option", "expected"),
    [
        (["--browsers", "all"], "-m playwright install chromium firefox webkit"),
        (["--browsers", "firefox"], "-m playwright install firefox"),
        (["--with-deps"], "-m playwright install --with-deps chromium"),
    ],
)
def test_browser_options(machine, option, expected):
    recorder = Recorder()
    bootstrap.main(option, machine, recorder)
    assert expected in words(recorder)


def test_options_that_skip_steps(machine):
    recorder = Recorder()
    bootstrap.main(["--browsers", "none", "--no-hooks", "--no-install"], machine, recorder)
    assert words(recorder) == ["tools/check_env.py", "tools/fingerprint.py", "tools/check_rules.py"]


def test_the_full_option_adds_the_whole_gate_set(machine):
    recorder = Recorder()
    bootstrap.main(["--check", "--full"], machine, recorder)
    steps = " | ".join(words(recorder))
    for word in ("ruff check", "ruff format", "mypy", "tests_framework"):
        assert word in steps


def test_a_failing_step_fails_the_bootstrap_and_is_named(machine, capsys):
    assert bootstrap.main([], machine, Recorder(failing=["fingerprint"])) == 1
    out = capsys.readouterr().out
    assert "[FAILED] framework identical to its manifest" in out
    assert "bootstrap: FAILED (1): framework identical to its manifest" in out


def test_a_failing_install_is_reported(machine, capsys):
    assert bootstrap.main([], machine, Recorder(failing=["pip install"])) == 1
    assert "[FAILED] dependencies (requirements.lock)" in capsys.readouterr().out


def test_the_wrong_python_stops_everything_before_any_install(machine, capsys):
    write(machine, ".python-version", "2.7\n")
    recorder = Recorder()
    assert bootstrap.main([], machine, recorder) == 1
    assert recorder.commands == []
    assert "wanted 2.7" in capsys.readouterr().out


def test_the_python_version_check(tmp_path):
    report = bootstrap.Report()
    assert bootstrap.check_python(tmp_path, report, (3, 12)) is True  # nothing to compare with
    write(tmp_path, ".python-version", "3.12.4\n")
    assert bootstrap.check_python(tmp_path, report, (3, 12)) is True
    assert bootstrap.check_python(tmp_path, report, (3, 14)) is False


def test_a_missing_env_example_is_reported(machine):
    (machine / ".env.example").unlink()
    report = bootstrap.Report()
    bootstrap.ensure_env_file(machine, report)
    assert report.failures == [".env"]


def test_help_prints_the_usage(capsys):
    assert bootstrap.main(["--help"], ROOT, Recorder()) == 0
    assert "Set up this machine" in capsys.readouterr().out


class NoGitRunner(Recorder):
    """Like a downloaded ZIP: the hook installer reports that there is no .git folder."""

    def __call__(self, command, cwd):
        code, output = super().__call__(command, cwd)
        if command[-2:] == ["tools/hooks.py", "install"]:
            return 0, "not a git repository (no .git folder): hooks were not installed"
        return code, output


def test_a_zip_download_without_git_is_told_honestly_that_no_hooks_are_installed(machine, capsys):
    assert bootstrap.main([], machine, NoGitRunner()) == 0  # everything else works without git
    out = capsys.readouterr().out
    assert "[skipped] git hooks - no .git folder" in out
    assert "[ok] git hooks" not in out
    assert "Note: No .git folder (a downloaded ZIP?)" in out
    assert "git init" in out
    assert "bootstrap: ok." in out


def test_with_git_the_hook_step_is_a_plain_ok_and_has_no_note(machine, capsys):
    assert bootstrap.main([], machine, Recorder()) == 0
    out = capsys.readouterr().out
    assert "[ok] git hooks" in out
    assert "Note:" not in out
