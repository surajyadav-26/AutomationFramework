"""core.settings parsing and validation (no real .env or config files are read)."""

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
