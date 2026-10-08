"""core.reporting.allure_helpers and allure_report (theme injection, suite grouping)."""

from core.reporting.allure_helpers import suite_labels, write_environment_properties
from core.reporting.allure_report import THEME_SCRIPT, apply_theme, generate_and_open


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
