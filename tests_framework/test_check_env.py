"""tools/check_env.py: lock parsing, drift detection and the Python version check."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_env", ROOT / "tools" / "check_env.py")
check_env = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_env)


def test_names_are_normalised_the_way_pip_does():
    assert check_env.normalise("Pillow") == "pillow"
    assert check_env.normalise("pytest_bdd") == "pytest-bdd"
    assert check_env.normalise("zope.interface") == "zope-interface"


def test_pins_are_read_and_comments_or_blank_lines_ignored():
    text = "# header\n\nPillow==12.2.0\npytest_bdd==9.0.0\n-e .\nnot a pin\n"
    assert check_env.parse_pins(text) == {"pillow": "12.2.0", "pytest-bdd": "9.0.0"}


def test_direct_dependencies_are_read_without_versions_extras_or_comments():
    text = (
        "# comment\npytest\nrequests>=2.0  # note\nuvicorn[standard]==1\n-r other.txt\n\nPillow\n"
    )
    assert check_env.parse_direct(text) == ["pytest", "requests", "uvicorn", "pillow"]


def test_matching_environment_has_no_drift():
    assert check_env.drift_problems({"a": "1.0"}, {"a": "1.0", "extra": "9"}) == []


def test_missing_and_different_versions_are_reported():
    problems = check_env.drift_problems(
        {"a": "1.0", "b": "2.0", "c": "3.0"}, {"a": "1.0", "b": "2.1"}
    )
    assert problems == ["b: lock pins 2.0, installed 2.1", "c==3.0 is pinned but not installed"]


def test_direct_dependencies_must_be_pinned():
    assert check_env.unpinned_direct(["a", "b"], {"a": "1"}) == [
        "b is a direct dependency but is not pinned in a lock file"
    ]


@pytest.mark.parametrize(
    ("wanted", "actual", "expected_problem"),
    [("3.12", (3, 12), False), ("3.12.4\n", (3, 12), False), ("3.12", (3, 14), True)],
)
def test_python_version_is_compared_on_major_and_minor(wanted, actual, expected_problem):
    problem = check_env.python_problem(wanted, actual)
    assert bool(problem) is expected_problem
    if problem:
        assert "3.14" in problem


def test_installed_versions_include_pytest():
    assert "pytest" in check_env.installed_versions()


def test_every_direct_dependency_of_the_repo_is_pinned():
    pins = {}
    for lock in check_env.LOCKS:
        pins.update(check_env.parse_pins((ROOT / lock).read_text(encoding="utf-8")))
    direct = []
    for name in check_env.DIRECT:
        direct += check_env.parse_direct((ROOT / name).read_text(encoding="utf-8"))
    assert check_env.unpinned_direct(direct, pins) == []


def test_ci_takes_its_python_version_from_the_python_version_file():
    """One source of truth: the shared setup action and the report job read .python-version."""
    action = (ROOT / ".github" / "actions" / "setup" / "action.yml").read_text(encoding="utf-8")
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python-version-file: .python-version" in action
    assert "python-version-file: .python-version" in ci  # the report job sets Python up itself
    assert 'python-version: "' not in action + ci  # no second, hard-coded version to drift


# --- main(): the whole doctor against a throwaway project --------------------------------------


@pytest.fixture
def doctor(tmp_path, monkeypatch):
    """A tiny project root with a matching lock; returns a function that runs check_env.main()."""
    (tmp_path / ".python-version").write_text("3.12\n")
    (tmp_path / "requirements.lock").write_text("alpha==1.0\nbeta==2.0\ngamma==3.0\n")
    (tmp_path / "requirements.in").write_text("alpha\nbeta\ngamma\n")
    monkeypatch.setattr(check_env, "ROOT", tmp_path)
    monkeypatch.setattr(check_env.sys, "version_info", (3, 12, 4, "final", 0))
    installed = {"alpha": "1.0", "beta": "2.0", "gamma": "3.0"}
    monkeypatch.setattr(check_env, "installed_versions", lambda: installed)

    def run():
        return check_env.main()

    run.root = tmp_path
    run.installed = installed
    return run


def test_a_matching_environment_passes(doctor, capsys):
    assert doctor() == 0
    assert "check_env: ok (3 pinned, 0 problem(s))" in capsys.readouterr().out


def test_drift_fails_and_names_the_package(doctor, capsys):
    doctor.installed["beta"] = "2.5"
    assert doctor() == 1
    out = capsys.readouterr().out
    assert "beta: lock pins 2.0, installed 2.5" in out
    assert "FAILED" in out


def test_a_wrong_python_version_fails(doctor, monkeypatch, capsys):
    monkeypatch.setattr(check_env.sys, "version_info", (3, 14, 0, "final", 0))
    assert doctor() == 1
    assert "Python 3.14 is running, .python-version asks for 3.12" in capsys.readouterr().out


def test_a_direct_dependency_missing_from_the_locks_fails(doctor, capsys):
    (doctor.root / "requirements.in").write_text("alpha\nbeta\ndelta\n")
    assert doctor() == 1
    assert "delta is a direct dependency but is not pinned" in capsys.readouterr().out


def test_a_clashing_package_only_warns(doctor, capsys):
    doctor.installed["allure-pytest"] = "2.16.0"
    assert doctor() == 0
    out = capsys.readouterr().out
    assert "warning: allure-pytest 2.16.0 is installed" in out
    assert "check_env: ok" in out


def test_missing_optional_files_are_tolerated(doctor, capsys):
    (doctor.root / ".python-version").unlink()
    (doctor.root / "requirements.in").unlink()
    assert doctor() == 0
