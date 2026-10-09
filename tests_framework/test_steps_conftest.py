"""steps/conftest.py: the shared cleanup fixture, end to end.

The cleanup tests run a real pytest session that uses the project's own steps/conftest.py.
"""

from pathlib import Path

import pytest

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


def test_a_session_without_allure_still_runs(project):
    project.makepyfile(
        """
        def test_it(cleanup):
            pass
        """
    )
    project.runpytest_subprocess(*INNER_ARGS).assert_outcomes(passed=1)
