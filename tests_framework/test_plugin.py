"""core.areas and core.reporting.plugin: areas, --area, grouping, hooks, session end, real wiring.

Most tests drive the hook functions directly with small fakes; the last section runs real pytest
sessions that use the project's own root conftest.py to prove the plugins are wired.
"""

import contextlib
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import areas
from core.reporting import plugin
from core.settings import MissingSettingError

ROOT = Path(__file__).resolve().parent.parent


# --- areas ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/p/steps/ui/auth/test_login_steps.py", "auth"),
        ("/p/steps/api/cart/test_x.py", "cart"),
        ("/home/steps/work/steps/visual/checkout/test_x.py", "checkout"),  # the innermost steps/
        ("/p/steps/ui/test_x.py", None),  # no area folder
        ("/p/steps/other/auth/test_x.py", None),  # not a suite
        ("/p/tests/ui/auth/test_x.py", None),  # not under steps/
    ],
)
def test_the_area_is_the_folder_below_the_suite(path, expected):
    assert areas.area_of(Path(path)) == expected


def test_areas_are_discovered_from_the_features_folder(tmp_path):
    for folder in ("ui/auth", "api/auth", "ui/cart", "ui/_private"):
        (tmp_path / "features" / folder).mkdir(parents=True)
    (tmp_path / "features" / "ui" / "a_file.feature").write_text("x")
    assert areas.discover_areas(tmp_path) == ["auth", "cart"]
    assert areas.discover_areas(tmp_path / "nothing") == []


@pytest.mark.parametrize(
    ("name", "valid"),
    [("auth", True), ("cart_items", True), ("Auth", False), ("ui", False), ("smoke", False),
     ("shared", False), ("components", False), ("_x", False), ("a-b", False), ("1a", False)],
)  # fmt: skip
def test_area_names_are_lowercase_identifiers_that_are_not_reserved(name, valid):
    assert areas.is_valid_area_name(name) is valid


# --- collection hook -----------------------------------------------------------------------------


class FakeItem:
    def __init__(self, path, markers=("ui",), browser=None):
        self.path = Path(path)
        self.nodeid = f"{path}::test"
        self._markers = list(markers)
        self.callspec = SimpleNamespace(params={"browser_name": browser}) if browser else None
        self.added = []

    def iter_markers(self):
        return [SimpleNamespace(name=m) for m in self._markers]

    def get_closest_marker(self, name):
        return SimpleNamespace(name=name) if name in self._markers else None

    def add_marker(self, mark):
        self.added.append(mark)


class FakeConfig:
    def __init__(self, **options):
        defaults = {
            "area": [], "markexpr": "", "browser": [], "reruns": None, "reruns_delay": None,
            "tracing": "off", "video": "off", "allure_report_dir": None, "collectonly": False,
        }  # fmt: skip
        self.option = SimpleNamespace(**{**defaults, **options})
        self.rootpath = options.get("rootpath", Path("."))
        self.deselected = []
        self.markers = []
        self.hook = SimpleNamespace(pytest_deselected=lambda items: self.deselected.extend(items))

    def getoption(self, name, default=None):
        return getattr(self.option, name.replace("-", "_"), default)

    def addinivalue_line(self, name, line):
        self.markers.append((name, line))


@pytest.fixture
def recorded(monkeypatch):
    calls = []

    def fake_marks(markers, area, name, smoke_run):
        calls.append((sorted(markers), area, name, smoke_run))
        return ["suite-mark"]

    monkeypatch.setattr(plugin, "suite_marks", fake_marks)
    return calls


def test_every_test_gets_its_area_marker_and_the_report_grouping(recorded):
    item = FakeItem("/p/steps/ui/auth/test_login_steps.py")
    plugin.pytest_collection_modifyitems(FakeConfig(), [item])
    assert recorded == [(["ui"], "Auth", "Login", False)]
    assert [getattr(m, "name", m) for m in item.added] == ["auth", "suite-mark"]


def test_multi_word_areas_and_names_are_title_cased(recorded):
    item = FakeItem("/p/steps/visual/order_history/test_login_visual_steps.py", ["visual"])
    plugin.pytest_collection_modifyitems(FakeConfig(), [item])
    assert recorded == [(["visual"], "Order History", "Login Visual", False)]


def test_a_test_outside_the_layout_gets_no_area_marker(recorded):
    item = FakeItem("/p/somewhere/test_thing.py")
    plugin.pytest_collection_modifyitems(FakeConfig(), [item])
    assert recorded == [(["ui"], None, "Thing", False)]
    assert item.added == ["suite-mark"]


def test_smoke_runs_are_detected_from_the_marker_expression(recorded):
    for expression in ("smoke", "not smoke", "ui and smoke", ""):
        plugin.pytest_collection_modifyitems(
            FakeConfig(markexpr=expression), [FakeItem("/p/steps/api/auth/test_user_steps.py")]
        )
    assert [call[3] for call in recorded] == [True, False, True, False]


def test_the_browser_is_added_only_for_multi_browser_runs(recorded):
    item = FakeItem("/p/steps/ui/auth/test_login_steps.py", browser="firefox")
    plugin.pytest_collection_modifyitems(FakeConfig(browser=["chromium", "firefox"]), [item])
    plugin.pytest_collection_modifyitems(FakeConfig(browser=["firefox"]), [item])
    assert [call[1] for call in recorded] == ["Auth (firefox)", "Auth"]


def test_the_browser_goes_on_the_name_when_there_is_no_area(recorded):
    item = FakeItem("/p/loose/test_login_steps.py", browser="webkit")
    plugin.pytest_collection_modifyitems(FakeConfig(browser=["chromium", "webkit"]), [item])
    assert recorded == [(["ui"], None, "Login (webkit)", False)]


def test_area_option_keeps_only_that_area_and_reports_the_rest_as_deselected(recorded):
    auth = FakeItem("/p/steps/ui/auth/test_login_steps.py")
    cart = FakeItem("/p/steps/ui/cart/test_cart_steps.py")
    loose = FakeItem("/p/other/test_x.py")
    items = [auth, cart, loose]
    config = FakeConfig(area=["cart"])
    plugin.pytest_collection_modifyitems(config, items)
    assert items == [cart]
    assert config.deselected == [auth, loose]


def test_several_areas_can_be_selected(recorded):
    items = [
        FakeItem("/p/steps/ui/auth/test_a_steps.py"),
        FakeItem("/p/steps/ui/cart/test_b_steps.py"),
        FakeItem("/p/steps/ui/pay/test_c_steps.py"),
    ]
    plugin.pytest_collection_modifyitems(FakeConfig(area=["auth", "pay"]), items)
    assert [i.path.parent.name for i in items] == ["auth", "pay"]


def test_without_the_area_option_nothing_is_deselected(recorded):
    items = [FakeItem("/p/steps/ui/auth/test_a_steps.py"), FakeItem("/p/other/test_b.py")]
    config = FakeConfig()
    plugin.pytest_collection_modifyitems(config, items)
    assert len(items) == 2
    assert config.deselected == []


def test_inactive_allure_placeholders_are_skipped_instead_of_crashing(monkeypatch):
    monkeypatch.setattr(plugin, "suite_marks", lambda *args: [lambda fn: fn])
    item = FakeItem("/p/steps/ui/auth/test_login_steps.py")
    plugin.pytest_collection_modifyitems(FakeConfig(), [item])
    assert [getattr(m, "name", m) for m in item.added] == ["auth"]  # only the real area marker


# --- configure -----------------------------------------------------------------------------------


@pytest.fixture
def configured(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        rerun_count=2, rerun_delay=0.5, trace_mode="on", video_mode="retain-on-failure",
        log_retention_days=7,
    )  # fmt: skip
    purged = []
    monkeypatch.setattr(plugin, "get_settings", lambda: settings)
    monkeypatch.setattr(plugin, "daily_log_path", lambda: tmp_path / "application-x.log")
    monkeypatch.setattr(plugin, "purge_old_logs", lambda days: purged.append(days))
    return SimpleNamespace(settings=settings, purged=purged, log=tmp_path / "application-x.log")


def test_configure_applies_the_settings_to_the_run(configured, tmp_path):
    config = FakeConfig(rootpath=tmp_path)
    plugin.pytest_configure(config)
    option = config.option
    assert (option.reruns, option.reruns_delay) == (2, 0.5)
    assert (option.tracing, option.video) == ("on", "retain-on-failure")
    assert option.log_file == str(configured.log)
    assert option.log_file_mode == "a"
    assert configured.purged == [7]


def test_explicit_command_line_values_win_over_the_settings(configured, tmp_path):
    config = FakeConfig(rootpath=tmp_path, reruns=0, reruns_delay=9, tracing="off", video="on")
    plugin.pytest_configure(config)
    assert (config.option.reruns, config.option.reruns_delay) == (0, 9)
    assert config.option.video == "on"  # not "off", so it is left alone


def test_workers_do_not_purge_the_logs(configured, tmp_path):
    config = FakeConfig(rootpath=tmp_path)
    config.workerinput = {}
    plugin.pytest_configure(config)
    assert configured.purged == []


def test_the_areas_found_in_features_are_registered_as_markers(configured, tmp_path):
    (tmp_path / "features" / "ui" / "auth").mkdir(parents=True)
    (tmp_path / "features" / "api" / "cart").mkdir(parents=True)
    config = FakeConfig(rootpath=tmp_path)
    plugin.pytest_configure(config)
    registered = [line.split(":")[0] for _, line in config.markers]
    assert registered == ["auth", "cart"]


def test_an_unknown_area_is_a_usage_error_that_lists_the_known_ones(configured, tmp_path):
    (tmp_path / "features" / "ui" / "auth").mkdir(parents=True)
    config = FakeConfig(rootpath=tmp_path, area=["nope"])
    with pytest.raises(pytest.UsageError, match=r"unknown area \['nope'\].*\['auth'\]"):
        plugin.pytest_configure(config)


def test_bad_settings_become_a_clean_usage_error(monkeypatch, tmp_path):
    def broken():
        raise MissingSettingError("API_MODE='x' is invalid")

    monkeypatch.setattr(plugin, "get_settings", broken)
    with pytest.raises(pytest.UsageError, match="API_MODE"):
        plugin.pytest_configure(FakeConfig(rootpath=tmp_path))


# --- failure screenshot and trace attachments -----------------------------------------------------


def drive(hook, *args, result=None):
    """Run a hookwrapper generator: code before the yield, then the part after it."""
    generator = hook(*args)
    next(generator)
    with contextlib.suppress(StopIteration):
        generator.send(result)


def outcome_of(report):
    return SimpleNamespace(get_result=lambda: report)


class FakePage:
    def __init__(self, fail=False):
        self.fail = fail

    def screenshot(self, full_page):
        if self.fail:
            raise RuntimeError("browser is gone")
        return b"png-bytes"


@pytest.fixture
def screenshots(monkeypatch):
    taken = []
    monkeypatch.setattr(plugin, "attach_png", lambda data, name: taken.append((data, name)))
    return taken


def failed_call():
    return SimpleNamespace(when="call", failed=True)


def test_a_failing_browser_test_attaches_a_full_page_screenshot(monkeypatch, screenshots):
    monkeypatch.setattr(plugin, "_fixture", lambda item, name: FakePage())
    drive(plugin.pytest_runtest_makereport, FakeItem("/p/x.py", ["ui"]), None,
          result=outcome_of(failed_call()))  # fmt: skip
    assert screenshots == [(b"png-bytes", "Failure screenshot")]


@pytest.mark.parametrize(
    ("markers", "report"),
    [
        (["api"], failed_call()),  # not a browser test
        (["ui"], SimpleNamespace(when="setup", failed=True)),  # not the call phase
        (["ui"], SimpleNamespace(when="call", failed=False)),  # passed
    ],
)
def test_no_screenshot_when_it_makes_no_sense(monkeypatch, screenshots, markers, report):
    monkeypatch.setattr(plugin, "_fixture", lambda item, name: FakePage())
    drive(plugin.pytest_runtest_makereport, FakeItem("/p/x.py", markers), None,
          result=outcome_of(report))  # fmt: skip
    assert screenshots == []


def test_a_broken_browser_never_breaks_the_report(monkeypatch, screenshots, caplog):
    monkeypatch.setattr(plugin, "_fixture", lambda item, name: FakePage(fail=True))
    with caplog.at_level(logging.ERROR, logger="hooks"):
        drive(plugin.pytest_runtest_makereport, FakeItem("/p/x.py", ["visual"]), None,
              result=outcome_of(failed_call()))  # fmt: skip
    assert screenshots == []
    assert "could not capture failure screenshot" in caplog.text


def test_fixture_lookup_refuses_items_that_are_not_test_functions():
    with pytest.raises(LookupError, match="not a test function"):
        plugin._fixture(FakeItem("/p/x.py"), "page")


@pytest.fixture
def media(monkeypatch, tmp_path):
    attached = []
    folder = tmp_path / "output"
    folder.mkdir()
    (folder / "trace.zip").write_bytes(b"zip")
    (folder / "video.webm").write_bytes(b"webm")
    monkeypatch.setattr(plugin, "attach_file", lambda *args: attached.append(args[1:]))
    monkeypatch.setattr(plugin, "_fixture", lambda item, name: str(folder))
    monkeypatch.setattr(
        plugin, "get_settings", lambda: SimpleNamespace(attach_trace_and_video=True)
    )
    return SimpleNamespace(attached=attached, folder=folder, monkeypatch=monkeypatch)


def test_trace_and_video_are_attached_after_the_test_has_finished(media):
    drive(plugin.pytest_runtest_teardown, FakeItem("/p/x.py", ["ui"]))
    assert [(title[:19], mime, ext) for title, mime, ext in media.attached] == [
        ("Playwright trace (p", "application/zip", "zip"),
        ("Playwright video", "video/webm", "webm"),
    ]


def test_only_the_files_that_exist_are_attached(media):
    (media.folder / "video.webm").unlink()
    drive(plugin.pytest_runtest_teardown, FakeItem("/p/x.py", ["accessibility"]))
    assert len(media.attached) == 1


def test_nothing_is_attached_when_the_switch_is_off_or_for_api_tests(media):
    media.monkeypatch.setattr(
        plugin, "get_settings", lambda: SimpleNamespace(attach_trace_and_video=False)
    )
    drive(plugin.pytest_runtest_teardown, FakeItem("/p/x.py", ["ui"]))
    media.monkeypatch.setattr(
        plugin, "get_settings", lambda: SimpleNamespace(attach_trace_and_video=True)
    )
    drive(plugin.pytest_runtest_teardown, FakeItem("/p/x.py", ["api"]))
    assert media.attached == []


def test_a_missing_output_folder_is_logged_not_raised(media, caplog):
    def broken(item, name):
        raise RuntimeError("fixture is gone")

    media.monkeypatch.setattr(plugin, "_fixture", broken)
    with caplog.at_level(logging.ERROR, logger="hooks"):
        drive(plugin.pytest_runtest_teardown, FakeItem("/p/x.py", ["ui"]))
    assert media.attached == []
    assert "could not find the Playwright output folder" in caplog.text


# --- end of session ------------------------------------------------------------------------------


@pytest.fixture
def finishing(monkeypatch, tmp_path):
    opened = []
    settings = SimpleNamespace(
        env="qa", app_url="https://app", api_url="https://api", allure_auto_open=True,
        allure_theme="dark",
    )  # fmt: skip
    monkeypatch.setattr(plugin, "get_settings", lambda: settings)

    def fake_generate(results, report, theme):
        opened.append((results, report, theme))
        return "opened"

    monkeypatch.setattr(plugin, "generate_and_open", fake_generate)
    results = tmp_path / "reports" / "allure-results"
    config = FakeConfig(allure_report_dir=str(results), browser=["firefox", "webkit"])
    session = SimpleNamespace(config=config, testscollected=3)
    return SimpleNamespace(settings=settings, opened=opened, results=results, session=session)


def test_the_environment_file_is_written_and_the_report_is_opened(finishing, capsys):
    plugin.pytest_sessionfinish(finishing.session)
    text = (finishing.results / "environment.properties").read_text(encoding="utf-8")
    assert "env=qa" in text
    assert "browser=firefox, webkit" in text
    assert finishing.opened == [
        (finishing.results, finishing.results.parent / "allure-report", "dark")
    ]
    assert "opened" in capsys.readouterr().out


def test_the_report_is_not_opened_when_it_should_not_be(finishing):
    finishing.settings.allure_auto_open = False
    plugin.pytest_sessionfinish(finishing.session)
    finishing.settings.allure_auto_open = True
    finishing.session.testscollected = 0
    plugin.pytest_sessionfinish(finishing.session)
    finishing.session.testscollected = 3
    finishing.session.config.option.collectonly = True
    plugin.pytest_sessionfinish(finishing.session)
    assert finishing.opened == []


def test_a_worker_or_a_run_without_allure_writes_nothing(finishing):
    finishing.session.config.workerinput = {}
    plugin.pytest_sessionfinish(finishing.session)
    del finishing.session.config.workerinput
    finishing.session.config.option.allure_report_dir = None
    plugin.pytest_sessionfinish(finishing.session)
    assert not finishing.results.exists()
    assert finishing.opened == []


def test_the_default_browser_is_named_when_none_was_chosen(finishing):
    finishing.session.config.option.browser = []
    plugin.pytest_sessionfinish(finishing.session)
    assert "browser=chromium" in (finishing.results / "environment.properties").read_text()


class FakeReporter:
    def __init__(self, stats):
        self.stats = stats
        self.lines = []

    def section(self, title):
        self.lines.append(f"## {title}")

    def line(self, text):
        self.lines.append(text)


def test_retried_tests_are_listed_once_each():
    reporter = FakeReporter({"rerun": [SimpleNamespace(nodeid="b"), SimpleNamespace(nodeid="a"),
                                       SimpleNamespace(nodeid="b")]})  # fmt: skip
    plugin.pytest_terminal_summary(reporter)
    assert reporter.lines == ["## retried after infrastructure errors", "a", "b"]


def test_nothing_is_printed_when_nothing_was_retried():
    reporter = FakeReporter({})
    plugin.pytest_terminal_summary(reporter)
    assert reporter.lines == []


# --- real sessions that use the project's own root conftest.py ----------------------------------


@pytest.fixture
def session_project(pytester, monkeypatch):
    """A throwaway project wired exactly like the framework: the real root conftest.py."""
    monkeypatch.setenv("PYTHONPATH", str(ROOT))
    monkeypatch.setenv("ALLURE_AUTO_OPEN", "false")
    pytester.makeconftest((ROOT / "conftest.py").read_text(encoding="utf-8"))
    for area in ("auth", "cart"):
        (pytester.path / "features" / "ui" / area).mkdir(parents=True)
        folder = pytester.path / "steps" / "ui" / area
        folder.mkdir(parents=True)
        (folder / f"test_{area}.py").write_text("def test_it():\n    pass\n", encoding="utf-8")
    return pytester


INNER = ("-p", "no:allure_pytest", "--strict-markers", "-p", "no:cacheprovider")


def test_the_area_option_selects_one_area_end_to_end(session_project):
    result = session_project.runpytest_subprocess(*INNER, "--area", "cart", "-v")
    result.assert_outcomes(passed=1, deselected=1)
    result.stdout.fnmatch_lines(["*steps/ui/cart/test_cart.py::test_it PASSED*"])


def test_area_markers_work_with_strict_markers(session_project):
    result = session_project.runpytest_subprocess(*INNER, "-m", "auth")
    result.assert_outcomes(passed=1, deselected=1)


def test_an_unknown_area_stops_the_run_with_a_clear_message(session_project):
    result = session_project.runpytest_subprocess(*INNER, "--area", "nope")
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*unknown area*nope*known areas*auth*cart*"])


def test_reruns_come_from_the_environment_and_retried_tests_are_listed(
    session_project, monkeypatch
):
    monkeypatch.setenv("RERUN_COUNT", "1")
    monkeypatch.setenv("RERUN_DELAY", "0")
    (session_project.path / "steps" / "ui" / "auth" / "test_auth.py").write_text(
        "import requests\n\n\ndef test_it():\n"
        "    raise requests.exceptions.ConnectionError('down')\n",
        encoding="utf-8",
    )
    result = session_project.runpytest_subprocess(
        *INNER, "--only-rerun=^(ConnectionError):", "--area", "auth"
    )
    outcomes = result.parseoutcomes()
    assert (outcomes["failed"], outcomes["rerun"]) == (1, 1)
    result.stdout.fnmatch_lines(
        ["*retried after infrastructure errors*", "*test_auth.py::test_it*"]
    )


def test_a_setting_error_is_reported_without_a_traceback(session_project, monkeypatch):
    monkeypatch.setenv("API_MODE", "bogus")
    result = session_project.runpytest_subprocess(*INNER)
    assert result.ret != 0
    result.stderr.fnmatch_lines(["*API_MODE='bogus' is invalid*"])
    assert "Traceback" not in result.stderr.str()
