"""tools/ci_summary.py on synthetic Allure results."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ci_summary", ROOT / "tools" / "ci_summary.py")
ci_summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_summary)


def result(directory, name, status, parent, suite, message=None):
    body = {
        "name": name,
        "status": status,
        "labels": [
            {"name": "parentSuite", "value": parent},
            {"name": "suite", "value": suite},
        ],
    }
    if message:
        body["statusDetails"] = {"message": message}
    (directory / f"{name.replace(' ', '_')}-result.json").write_text(json.dumps(body))


def test_empty_folder_is_reported_not_an_error(tmp_path):
    assert "No Allure results" in ci_summary.summarize(tmp_path)
    assert "No Allure results" in ci_summary.summarize(tmp_path / "missing")


def test_counts_and_groups(tmp_path):
    result(tmp_path, "a", "passed", "UI", "Login")
    result(tmp_path, "b", "passed", "UI", "Login")
    result(tmp_path, "c", "failed", "API", "User", "AssertionError: assert 400 == 200\nmore")
    text = ci_summary.summarize(tmp_path)
    assert "**3 tests**: 2 passed, 1 failed" in text
    assert "| UI / Login | 2 | 0 | 0 | 0 |" in text
    assert "| API / User | 0 | 1 | 0 | 0 |" in text


def test_failures_are_listed_with_the_first_message_line(tmp_path):
    result(tmp_path, "bad one", "broken", "UI", "Login", "TimeoutError: boom\nsecond line")
    text = ci_summary.summarize(tmp_path)
    assert "#### Failures" in text
    assert "bad one" in text
    assert "`TimeoutError: boom`" in text
    assert "second line" not in text


def test_no_failure_section_when_everything_passes(tmp_path):
    result(tmp_path, "a", "passed", "UI", "Login")
    assert "Failures" not in ci_summary.summarize(tmp_path)


def test_a_corrupt_result_file_is_ignored(tmp_path):
    result(tmp_path, "a", "passed", "UI", "Login")
    (tmp_path / "broken-result.json").write_text("{not json")
    assert "**1 tests**" in ci_summary.summarize(tmp_path)


def test_main_prints_and_returns_zero(tmp_path, capsys):
    result(tmp_path, "a", "passed", "UI", "Login")
    assert ci_summary.main(["ci_summary", str(tmp_path)]) == 0
    assert "Test results" in capsys.readouterr().out
