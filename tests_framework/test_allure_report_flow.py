"""Generating and opening the Allure report, and the attach helpers, with everything faked."""

import subprocess
from types import SimpleNamespace

import pytest

from core.reporting import allure_helpers, allure_report
from core.reporting.allure_report import generate_and_open


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


# --- attach helpers ---------------------------------------------------------------------------


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
