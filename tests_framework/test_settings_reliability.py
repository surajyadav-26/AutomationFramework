"""Reliability settings: API timeout, API mode, rerun count and delay."""

import pytest

from core import settings as settings_module
from core.settings import MissingSettingError, get_settings

KEYS = ["TEST_ENV", "API_TIMEOUT", "API_MODE", "RERUN_COUNT", "RERUN_DELAY"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("APP_URL", "https://app.example")
    monkeypatch.setenv("API_URL", "https://api.example")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
