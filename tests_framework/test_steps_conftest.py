"""steps/conftest.py: the shared cleanup fixture (end to end) and the report grouping hook.

The cleanup tests run a real pytest session that uses the project's own steps/conftest.py.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from steps import conftest as steps_conftest

ROOT = Path(__file__).resolve().parent.parent
# an old global allure-pytest clashes with allure-pytest-bdd; harmless when it is not installed
INNER_ARGS = ("-p", "no:allure_pytest")


@pytest.fixture
def project(pytester, monkeypatch):
    """A throwaway pytest project using the real shared conftest of the framework.

    The inner session runs in its own process: the Playwright pytest plugin keeps global state that
    cannot be nested inside the session that is running these tests.
    """
    monkeypatch.setenv("PYTHONPATH", str(ROOT))  # so the copied conftest can import core/
    pytester.makeconftest((ROOT / "steps" / "conftest.py").read_text(encoding="utf-8"))
    return pytester


def test_cleanup_callbacks_run_when_the_test_passes(project):
    project.makepyfile(
        """
        def test_it(cleanup):
            cleanup.register(lambda: open("ran.txt", "w").write("yes"))
        """
    )
    project.runpytest_subprocess(*INNER_ARGS).assert_outcomes(passed=1)
    assert (project.path / "ran.txt").read_text() == "yes"


def test_cleanup_callbacks_run_even_when_the_test_fails(project):
    project.makepyfile(
        """
        def test_it(cleanup):
            cleanup.register(lambda: open("ran.txt", "w").write("yes"))
            assert False, "the test itself fails"
        """
    )
    project.runpytest_subprocess(*INNER_ARGS).assert_outcomes(failed=1)
    assert (project.path / "ran.txt").read_text() == "yes"


def test_callbacks_run_in_reverse_order_and_a_failing_one_does_not_stop_the_rest(project):
    project.makepyfile(
        """
        def test_it(cleanup):
            def boom():
                raise RuntimeError("cleanup broke")
            cleanup.register(lambda: open("log.txt", "a").write("first "))
            cleanup.register(boom, "boom")
            cleanup.register(lambda: open("log.txt", "a").write("last "))
        """
    )
    result = project.runpytest_subprocess(*INNER_ARGS)
    result.assert_outcomes(passed=1, errors=1)  # the broken cleanup is reported, not hidden
    result.stdout.fnmatch_lines(["*cleanup callbacks failed*boom*"])
    assert (project.path / "log.txt").read_text() == "last first "


def test_the_registry_is_fresh_for_every_test(project):
    project.makepyfile(
        """
        def test_one(cleanup):
            cleanup.register(lambda: open("count.txt", "a").write("x"))

        def test_two(cleanup):
            pass
        """
    )
    project.runpytest_subprocess(*INNER_ARGS).assert_outcomes(passed=2)
    assert (project.path / "count.txt").read_text() == "x"  # test_two did not re-run it


# --- report grouping hook ----------------------------------------------------------------------


class FakeItem:
    def __init__(self, path, markers, browser=None):
        self.path = Path(path)
        self._markers = markers
        self.callspec = SimpleNamespace(params={"browser_name": browser}) if browser else None
        self.added = []

    def iter_markers(self):
        return [SimpleNamespace(name=m) for m in self._markers]

    def add_marker(self, mark):
        self.added.append(mark)


class FakeConfig:
    def __init__(self, markexpr="", browsers=()):
        self.options = {"markexpr": markexpr, "browser": list(browsers)}

    def getoption(self, name):
        return self.options[name]


@pytest.fixture
def recorded(monkeypatch):
    calls = []
    monkeypatch.setattr(
        steps_conftest,
        "suite_marks",
        lambda markers, area, smoke: calls.append((sorted(markers), area, smoke)) or ["mark"],
    )
    return calls


def test_area_comes_from_the_step_file_name(recorded):
    item = FakeItem("steps/ui/test_login_visual_steps.py", ["ui"])
    steps_conftest.pytest_collection_modifyitems(FakeConfig(), [item])
    assert recorded == [(["ui"], "Login Visual", False)]
    assert item.added == ["mark"]


def test_smoke_runs_are_detected_from_the_marker_expression(recorded):
    steps_conftest.pytest_collection_modifyitems(
        FakeConfig(markexpr="smoke"), [FakeItem("steps/api/test_user_steps.py", ["api"])]
    )
    steps_conftest.pytest_collection_modifyitems(
        FakeConfig(markexpr="not smoke"), [FakeItem("steps/api/test_user_steps.py", ["api"])]
    )
    assert [call[2] for call in recorded] == [True, False]


def test_the_browser_is_added_only_for_multi_browser_runs(recorded):
    item = FakeItem("steps/ui/test_login_steps.py", ["ui"], browser="firefox")
    steps_conftest.pytest_collection_modifyitems(
        FakeConfig(browsers=["chromium", "firefox"]), [item]
    )
    steps_conftest.pytest_collection_modifyitems(FakeConfig(browsers=["firefox"]), [item])
    assert [call[1] for call in recorded] == ["Login (firefox)", "Login"]


def test_inactive_allure_placeholders_are_skipped_instead_of_crashing(monkeypatch):
    monkeypatch.setattr(steps_conftest, "suite_marks", lambda *args: [lambda fn: fn])
    item = FakeItem("steps/ui/test_login_steps.py", ["ui"])
    steps_conftest.pytest_collection_modifyitems(FakeConfig(), [item])
    assert item.added == []


def test_a_session_without_allure_still_runs(project):
    project.makepyfile(
        """
        def test_it(cleanup):
            pass
        """
    )
    project.runpytest_subprocess(*INNER_ARGS).assert_outcomes(passed=1)
