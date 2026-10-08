"""Reporting: Allure helpers and report flow, the axe scanner (fake axe) and the CI summary."""

import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.accessibility import axe_scanner
from core.accessibility.axe_scanner import WCAG_TAGS, blocking, describe, scan
from core.reporting import allure_helpers, allure_report
from core.reporting.allure_helpers import suite_labels, write_environment_properties
from core.reporting.allure_report import THEME_SCRIPT, apply_theme, generate_and_open

# --- Allure suite grouping and environment properties --------------------------------------


def labels(markers, area, smoke_run):
    return suite_labels(markers, area, smoke_run)


def test_full_run_groups_by_suite_then_area():
    assert labels({"ui", "smoke"}, "Login", smoke_run=False) == [
        ("parentSuite", "UI"),
        ("suite", "Login"),
    ]


def test_smoke_run_nests_suites_under_smoke():
    assert labels({"api"}, "User", smoke_run=True) == [
        ("parentSuite", "Smoke"),
        ("suite", "API"),
        ("subSuite", "User"),
    ]


def test_every_suite_has_a_display_name_and_unknown_falls_back():
    names = {
        marker: labels({marker}, "A", smoke_run=False)[0][1]
        for marker in ("ui", "api", "visual", "accessibility")
    }
    assert names == {
        "ui": "UI",
        "api": "API",
        "visual": "Visual",
        "accessibility": "Accessibility",
    }
    assert labels({"smoke"}, "A", smoke_run=False)[0][1] == "Other"


def test_environment_properties_file(tmp_path):
    path = write_environment_properties(tmp_path / "results", {"env": "qa", "browser": "firefox"})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert "env=qa" in lines
    assert "browser=firefox" in lines
    assert any(line.startswith("python=") for line in lines)


def test_theme_script_is_injected_once_at_the_start_of_head(tmp_path):
    (tmp_path / "index.html").write_text("<html><head><title>x</title></head></html>")
    apply_theme(tmp_path, "dark")
    html = (tmp_path / "index.html").read_text()
    assert html.count(THEME_SCRIPT % "dark") == 1
    assert html.index("allure-theme") < html.index("<title>")


def test_theme_value_is_configurable(tmp_path):
    (tmp_path / "index.html").write_text("<head></head>")
    apply_theme(tmp_path, "light")
    assert "setItem('allure-theme','light')" in (tmp_path / "index.html").read_text()


def test_report_is_skipped_with_a_message_when_there_are_no_results(tmp_path):
    message = generate_and_open(tmp_path / "missing", tmp_path / "report", "dark")
    assert "not" in message  # CLI missing or no results; it never raises


# --- generating and opening the report, attach helpers -------------------------------------


@pytest.fixture
def results(tmp_path):
    folder = tmp_path / "allure-results"
    folder.mkdir()
    (folder / "abc-result.json").write_text("{}")
    return folder


@pytest.fixture
def fake_cli(monkeypatch, tmp_path):
    """allure CLI present; generate writes an index.html; open is recorded, not started."""
    record = {"run": [], "popen": []}
    monkeypatch.setattr(allure_report.shutil, "which", lambda name: "ALLURE")

    def fake_run(command, **kwargs):
        record["run"].append(command)
        report = command[command.index("-o") + 1]
        (tmp_path / "report").mkdir(exist_ok=True)
        (tmp_path / "report" / "index.html").write_text("<html><head></head></html>")
        assert report == str(tmp_path / "report")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(allure_report.subprocess, "run", fake_run)
    monkeypatch.setattr(
        allure_report.subprocess, "Popen", lambda command, **kwargs: record["popen"].append(kwargs)
    )
    return record


def test_missing_cli_is_reported_not_raised(monkeypatch, results, tmp_path):
    monkeypatch.setattr(allure_report.shutil, "which", lambda name: None)
    assert "not found" in generate_and_open(results, tmp_path / "report", "dark")


def test_empty_results_are_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(allure_report.shutil, "which", lambda name: "ALLURE")
    (tmp_path / "empty").mkdir()
    assert "no allure results" in generate_and_open(tmp_path / "empty", tmp_path / "r", "dark")


def test_generate_failure_is_reported(monkeypatch, results, tmp_path):
    monkeypatch.setattr(allure_report.shutil, "which", lambda name: "ALLURE")
    monkeypatch.setattr(
        allure_report.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    message = generate_and_open(results, tmp_path / "report", "dark")
    assert "generate failed" in message
    assert "boom" in message


def test_success_generates_themes_and_opens_without_a_console_window(
    monkeypatch, results, tmp_path, fake_cli
):
    monkeypatch.setattr(allure_report.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    message = generate_and_open(results, tmp_path / "report", "light")
    assert "opened" in message
    assert fake_cli["run"][0][:2] == ["ALLURE", "generate"]
    assert "--clean" in fake_cli["run"][0]
    assert "setItem('allure-theme','light')" in (tmp_path / "report" / "index.html").read_text()
    popen = fake_cli["popen"][0]
    assert popen["creationflags"] & 0x08000000
    assert popen["stdout"] is subprocess.DEVNULL


def test_non_windows_does_not_set_creation_flags(monkeypatch, results, tmp_path, fake_cli):
    monkeypatch.setattr(allure_report.sys, "platform", "linux")
    generate_and_open(results, tmp_path / "report", "dark")
    assert fake_cli["popen"][0]["creationflags"] == 0


# --- axe scanner with a fake axe -----------------------------------------------------------


def violation(rule, impact, nodes=1):
    return {"id": rule, "impact": impact, "help": f"{rule} help", "nodes": [{}] * nodes}


@pytest.fixture
def fake_axe(monkeypatch):
    calls = {}
    attachments = []

    class FakeAxe:
        def run(self, page, options=None):
            calls["page"] = page
            calls["options"] = options
            return SimpleNamespace(response={"violations": calls["violations"]})

    monkeypatch.setattr(axe_scanner, "Axe", FakeAxe)
    monkeypatch.setattr(axe_scanner, "attach_json", lambda data, name: attachments.append(name))
    calls["violations"] = []
    return calls, attachments


def test_scan_runs_only_the_wcag_tags_and_returns_every_violation(fake_axe):
    calls, attachments = fake_axe
    calls["violations"] = [violation("image-alt", "critical"), violation("region", "minor")]
    result = scan("PAGE")
    assert [v["id"] for v in result] == ["image-alt", "region"]
    assert calls["page"] == "PAGE"
    assert calls["options"] == {"runOnly": {"type": "tag", "values": WCAG_TAGS}}
    assert attachments == ["Accessibility violations (2)"]


def test_best_practice_rules_are_added_only_on_request(fake_axe):
    calls, _ = fake_axe
    scan("PAGE", include_best_practices=True)
    assert calls["options"]["runOnly"]["values"] == [*WCAG_TAGS, "best-practice"]
    scan("PAGE")
    assert calls["options"]["runOnly"]["values"] == WCAG_TAGS


def test_scan_with_no_violations(fake_axe):
    _, attachments = fake_axe
    assert scan("PAGE") == []
    assert attachments == ["Accessibility violations (0)"]


@pytest.mark.parametrize(
    ("threshold", "expected"),
    [
        ("critical", ["a"]),
        ("serious", ["a", "b"]),
        ("moderate", ["a", "b", "c"]),
        ("minor", ["a", "b", "c", "d"]),
    ],
)
def test_blocking_keeps_violations_at_or_above_the_threshold(threshold, expected):
    found = [
        violation("a", "critical"),
        violation("b", "serious"),
        violation("c", "moderate"),
        violation("d", "minor"),
    ]
    assert [v["id"] for v in blocking(found, threshold)] == expected


def test_a_violation_without_impact_counts_as_minor():
    found = [violation("x", None)]
    assert blocking(found, "minor") == found
    assert blocking(found, "moderate") == []


def test_describe_lists_rule_impact_count_and_help():
    text = describe([violation("image-alt", "critical", nodes=3), violation("label", "serious")])
    assert "image-alt (critical, 3 element(s)): image-alt help" in text
    assert "label (serious, 1 element(s)): label help" in text
    assert "; " in text


# --- CI job summary ------------------------------------------------------------------------


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


# --- attach helpers ----------------------------------------------------------------------


@pytest.fixture
def fake_allure(monkeypatch):
    calls = []

    class Attach:
        def __call__(self, body, name, attachment_type):
            calls.append(("attach", body, name, str(attachment_type)))

        def file(self, source, name, attachment_type, extension):
            calls.append(("file", source, name, attachment_type, extension))

    monkeypatch.setattr(allure_helpers, "allure", SimpleNamespace(attach=Attach()))
    return calls


def test_attach_png_json_and_file(fake_allure, tmp_path):
    allure_helpers.attach_png(b"png", "shot")
    allure_helpers.attach_json({"a": 1}, "body")
    allure_helpers.attach_file(tmp_path / "t.zip", "trace", "application/zip", "zip")
    kinds = [call[0] for call in fake_allure]
    assert kinds == ["attach", "attach", "file"]
    assert fake_allure[0][1:3] == (b"png", "shot")
    assert '"a": 1' in fake_allure[1][1]
    assert fake_allure[2][3:] == ("application/zip", "zip")
