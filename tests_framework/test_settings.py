"""core.settings: parsing, validation, defaults, and that every setting is documented.

The autouse fixture keeps the real .env and config files out of these tests; test_settings_files.py
covers the real file precedence.
"""

import re
from pathlib import Path

import pytest

from core import settings as settings_module
from core.settings import MissingSettingError, get_settings

KEYS = [
    "TEST_ENV",
    "APP_URL",
    "API_URL",
    "APP_PASSWORD",
    "API_PASSWORD",
    "LOG_RETENTION_DAYS",
    "TRACE_MODE",
    "VIDEO_MODE",
    "ALLURE_AUTO_OPEN",
    "ALLURE_THEME",
    "A11Y_FAIL_IMPACT",
    "A11Y_INCLUDE_BEST_PRACTICES",
    "API_TIMEOUT",
    "API_MODE",
    "RERUN_COUNT",
    "RERUN_DELAY",
    "ATTACH_TRACE_AND_VIDEO",
    "VISUAL_IGNORE_ANTIALIASING",
    "CI",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(settings_module, "dotenv_values", lambda *args, **kwargs: {})
    monkeypatch.setenv("APP_URL", "https://app.example")
    monkeypatch.setenv("API_URL", "https://api.example")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults():
    s = get_settings()
    assert s.env == "qa"
    assert (s.app_url, s.api_url) == ("https://app.example", "https://api.example")
    assert s.log_retention_days == 7
    assert s.trace_mode == s.video_mode == "retain-on-failure"
    assert s.allure_auto_open is True
    assert s.allure_theme == "dark"
    assert s.a11y_fail_impact == "serious"


def test_values_are_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("LOG_RETENTION_DAYS", "30")
    monkeypatch.setenv("TRACE_MODE", "ON")
    monkeypatch.setenv("ALLURE_THEME", "light")
    monkeypatch.setenv("A11Y_FAIL_IMPACT", "minor")
    s = get_settings()
    assert s.log_retention_days == 30
    assert s.trace_mode == "on"
    assert s.allure_theme == "light"
    assert s.a11y_fail_impact == "minor"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TRACE_MODE", "bogus"),
        ("VIDEO_MODE", "sometimes"),
        ("ALLURE_THEME", "blue"),
        ("A11Y_FAIL_IMPACT", "huge"),
        ("LOG_RETENTION_DAYS", "seven"),
        ("ALLURE_AUTO_OPEN", "maybe"),
    ],
)
def test_invalid_values_are_rejected_with_the_setting_name(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(MissingSettingError, match=name):
        get_settings()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("true", True), ("1", True), ("YES", True), ("false", False), ("0", False)],
)
def test_auto_open_boolean_parsing(monkeypatch, raw, expected):
    monkeypatch.setenv("ALLURE_AUTO_OPEN", raw)
    assert get_settings().allure_auto_open is expected


def test_auto_open_is_disabled_in_ci(monkeypatch):
    monkeypatch.setenv("ALLURE_AUTO_OPEN", "true")
    monkeypatch.setenv("CI", "true")
    assert get_settings().allure_auto_open is False


def test_missing_url_is_reported(monkeypatch):
    monkeypatch.delenv("APP_URL")
    with pytest.raises(MissingSettingError, match="APP_URL"):
        get_settings()


def test_unknown_environment_names_the_missing_file(monkeypatch):
    monkeypatch.setenv("TEST_ENV", "nowhere")
    with pytest.raises(MissingSettingError, match="unknown TEST_ENV 'nowhere'"):
        get_settings()


def test_passwords_come_only_from_the_environment_and_fail_clearly(monkeypatch):
    s = get_settings()
    with pytest.raises(MissingSettingError, match="APP_PASSWORD"):
        _ = s.app_password
    with pytest.raises(MissingSettingError, match="API_PASSWORD"):
        _ = s.api_password
    monkeypatch.setenv("APP_PASSWORD", "x")
    assert s.app_password == "x"


def test_repr_does_not_contain_passwords(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "super-secret")
    assert "super-secret" not in repr(get_settings())


ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def env(monkeypatch):
    """The monkeypatch that the autouse fixture above has already set up."""
    return monkeypatch


# --- reliability settings ------------------------------------------------------------


def test_defaults_match_the_previous_hardcoded_behaviour():
    s = get_settings()
    assert s.api_timeout == 15.0
    assert s.api_mode == "live"
    assert s.rerun_count == 1
    assert s.rerun_delay == 1.0


def test_values_can_be_changed(monkeypatch):
    monkeypatch.setenv("API_TIMEOUT", "2.5")
    monkeypatch.setenv("API_MODE", "STUB")
    monkeypatch.setenv("RERUN_COUNT", "0")
    monkeypatch.setenv("RERUN_DELAY", "0")
    s = get_settings()
    assert (s.api_timeout, s.api_mode, s.rerun_count, s.rerun_delay) == (2.5, "stub", 0, 0.0)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("API_TIMEOUT", "fast"),
        ("API_TIMEOUT", "0"),
        ("API_TIMEOUT", "-3"),
        ("API_MODE", "fake"),
        ("RERUN_COUNT", "one"),
        ("RERUN_DELAY", "soon"),
    ],
)
def test_bad_values_are_rejected_with_the_setting_name(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(MissingSettingError, match=name):
        get_settings()


# --- URL validation and the trace attachment switch --------------------------------------


@pytest.mark.parametrize("bad", ["app.example", "ftp://x", "https://has space.example", "//x"])
def test_malformed_urls_are_rejected(env, bad):
    env.setenv("APP_URL", bad)
    with pytest.raises(MissingSettingError, match="APP_URL"):
        get_settings()


def test_trailing_slash_is_normalised(env):
    env.setenv("API_URL", "https://api.example/")
    assert get_settings().api_url == "https://api.example"


def test_trace_and_video_attachment_defaults_on_and_can_be_switched_off(env):
    assert get_settings().attach_trace_and_video is True
    get_settings.cache_clear()
    env.setenv("ATTACH_TRACE_AND_VIDEO", "false")
    assert get_settings().attach_trace_and_video is False


# --- visual settings ----------------------------------------------------------------------


def test_antialiasing_is_off_by_default(env):
    assert get_settings().visual_ignore_antialiasing is False


def test_antialiasing_can_be_enabled(env):
    env.setenv("VISUAL_IGNORE_ANTIALIASING", "true")
    assert get_settings().visual_ignore_antialiasing is True


def test_antialiasing_rejects_garbage(env):
    env.setenv("VISUAL_IGNORE_ANTIALIASING", "sometimes")
    with pytest.raises(MissingSettingError, match="VISUAL_IGNORE_ANTIALIASING"):
        get_settings()


# --- documentation drift ------------------------------------------------------------------


def setting_names():
    source = (ROOT / "core" / "settings.py").read_text(encoding="utf-8")
    names = set(
        re.findall(r'_(?:choice|int|float|bool|require|require_url)\("([A-Z0-9_]+)"', source)
    )
    names |= set(re.findall(r'getenv\("([A-Z0-9_]+)"', source))
    return names - {"CI"}  # CI is set by the CI system, never by us


def test_every_setting_is_documented_in_the_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = sorted(name for name in setting_names() if name not in readme)
    assert missing == [], f"add these settings to README.md: {missing}"


def test_every_setting_is_in_env_example_or_a_config_file():
    documented = (ROOT / ".env.example").read_text(encoding="utf-8")
    for config in (ROOT / "config").glob("*.env"):
        documented += config.read_text(encoding="utf-8")
    missing = sorted(name for name in setting_names() if name not in documented)
    assert missing == [], f"add these settings to .env.example or config/*.env: {missing}"


def test_env_example_has_no_values_for_secrets():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in ("APP_PASSWORD", "API_PASSWORD"):
        assert re.search(rf"^{name}=$", text, re.M), f"{name} must be empty in .env.example"
