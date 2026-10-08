"""tools/mutation_check.py: the runner logic, and that every mutant still applies."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "mutation_check", ROOT / "tools" / "mutation_check.py"
)
mutation_check = importlib.util.module_from_spec(spec)
sys.modules["mutation_check"] = mutation_check  # dataclasses look the module up by name
spec.loader.exec_module(mutation_check)
Mutant = mutation_check.Mutant


@pytest.fixture
def project(tmp_path):
    (tmp_path / "code.py").write_text("def ok():\n    return 1 < 2\n", encoding="utf-8")
    return tmp_path


def mutant(old="1 < 2", new="1 > 2", label="flip"):
    return Mutant("code.py", old, new, label)


def test_a_mutant_that_makes_the_tests_fail_is_killed(project):
    def run_tests():  # "tests" pass only while the code says 1 < 2
        return "1 < 2" in (project / "code.py").read_text(encoding="utf-8")

    results = mutation_check.evaluate(project, [mutant()], run_tests)
    assert [r.status for r in results] == ["killed"]


def test_a_mutant_the_tests_do_not_notice_survives(project):
    results = mutation_check.evaluate(project, [mutant()], lambda: True)
    assert [r.status for r in results] == ["survived"]


def test_the_file_is_restored_after_every_mutant(project):
    original = (project / "code.py").read_bytes()
    mutation_check.evaluate(project, [mutant(), mutant(new="1 == 2")], lambda: True)
    assert (project / "code.py").read_bytes() == original


def test_the_file_is_restored_even_if_the_test_run_blows_up(project):
    original = (project / "code.py").read_bytes()
    calls = iter([True])  # the baseline run passes, the next one raises

    def run_tests():
        try:
            return next(calls)
        except StopIteration:
            raise KeyboardInterrupt from None

    with pytest.raises(KeyboardInterrupt):
        mutation_check.evaluate(project, [mutant()], run_tests)
    assert (project / "code.py").read_bytes() == original


def test_windows_line_endings_survive_a_round_trip(tmp_path):
    (tmp_path / "code.py").write_bytes(b"x = 1 < 2\r\ny = 3\r\n")
    mutation_check.evaluate(tmp_path, [Mutant("code.py", "1 < 2", "1 > 2", "m")], lambda: True)
    assert (tmp_path / "code.py").read_bytes() == b"x = 1 < 2\r\ny = 3\r\n"


def test_a_mutant_whose_text_is_gone_is_reported_stale_not_survived(project):
    results = mutation_check.evaluate(project, [mutant(old="text that is not there")], lambda: True)
    assert [r.status for r in results] == ["stale"]


def test_only_the_first_occurrence_is_mutated(tmp_path):
    (tmp_path / "code.py").write_text("a = 1\nb = 1\n", encoding="utf-8")
    seen = []

    def run_tests():
        seen.append((tmp_path / "code.py").read_text(encoding="utf-8"))
        return True

    mutation_check.evaluate(tmp_path, [Mutant("code.py", "= 1", "= 2", "m")], run_tests)
    assert seen[1] == "a = 2\nb = 1\n"


def test_failing_self_tests_stop_the_run_before_anything_is_mutated(project):
    with pytest.raises(RuntimeError, match="fail even without a mutation"):
        mutation_check.evaluate(project, [mutant()], lambda: False)
    assert "1 < 2" in (project / "code.py").read_text(encoding="utf-8")


def test_select_filters_by_label_or_file():
    mutants = [Mutant("core/a.py", "x", "y", "alpha thing"), Mutant("tools/b.py", "x", "y", "beta")]
    assert mutation_check.select(mutants, None) == mutants
    assert mutation_check.select(mutants, "alpha") == [mutants[0]]
    assert mutation_check.select(mutants, "tools/") == [mutants[1]]
    assert mutation_check.select(mutants, "nothing") == []


def test_every_mutant_still_applies_to_the_real_source():
    """When code is refactored a mutant can go stale; this fails first so the list gets updated."""
    stale = []
    for item in mutation_check.MUTANTS:
        text = (ROOT / item.file).read_text(encoding="utf-8")
        if item.old not in text:
            stale.append(item.label)
        assert item.old != item.new, item.label
    assert stale == []


def test_mutant_labels_are_unique_and_the_list_is_substantial():
    labels = [m.label for m in mutation_check.MUTANTS]
    assert len(labels) == len(set(labels))
    assert len(labels) >= 20
