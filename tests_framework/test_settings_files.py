"""Where settings come from: real env > .env.<TEST_ENV> > .env > config/<TEST_ENV>.env."""

import pytest

from core import settings as settings_module
from core.settings import MissingSettingError, get_settings

KEYS = ["TEST_ENV", "APP_URL", "API_URL", "APP_PASSWORD", "API_PASSWORD", "TRACE_MODE"]


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A throwaway project root with config files, using the real dotenv loading."""
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "qa.env").write_text(
        "APP_URL=https://qa.example\nAPI_URL=https://api-qa\n"
    )
    (tmp_path / "config" / "stage.env").write_text(
        "APP_URL=https://stage.example\nAPI_URL=https://api-stage\n"
    )
    monkeypatch.setattr(settings_module, "ROOT", tmp_path)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()
    for key in KEYS:  # load_dotenv writes into the real process environment
        monkeypatch.delenv(key, raising=False)


def test_default_environment_is_qa(project):
    s = get_settings()
    assert (s.env, s.app_url) == ("qa", "https://qa.example")


def test_test_env_can_come_from_dot_env(project):
    (project / ".env").write_text("TEST_ENV=stage\n")
    s = get_settings()
    assert (s.env, s.app_url, s.api_url) == ("stage", "https://stage.example", "https://api-stage")


def test_real_environment_variable_beats_dot_env_for_test_env(project, monkeypatch):
    (project / ".env").write_text("TEST_ENV=stage\n")
    monkeypatch.setenv("TEST_ENV", "qa")
    assert get_settings().env == "qa"


def test_per_environment_file_beats_shared_dot_env(project, monkeypatch):
    (project / ".env").write_text("TEST_ENV=stage\nAPP_PASSWORD=shared\n")
    (project / ".env.stage").write_text("APP_PASSWORD=stage-only\n")
    assert get_settings().app_password == "stage-only"


def test_shared_dot_env_is_used_when_there_is_no_per_environment_file(project):
    (project / ".env").write_text("APP_PASSWORD=shared\n")
    assert get_settings().app_password == "shared"


def test_other_environments_files_are_not_read(project):
    (project / ".env").write_text("APP_PASSWORD=shared\n")
    (project / ".env.stage").write_text("APP_PASSWORD=stage-only\n")
    assert get_settings().app_password == "shared"  # TEST_ENV is qa


def test_real_environment_beats_every_file(project, monkeypatch):
    (project / ".env").write_text("APP_PASSWORD=shared\nTRACE_MODE=off\n")
    (project / ".env.qa").write_text("APP_PASSWORD=qa-only\n")
    monkeypatch.setenv("APP_PASSWORD", "from-shell")
    s = get_settings()
    assert s.app_password == "from-shell"
    assert s.trace_mode == "off"


def test_urls_in_config_do_not_beat_secrets_files(project):
    (project / ".env.qa").write_text("APP_URL=https://override.example\n")
    assert get_settings().app_url == "https://override.example"


def test_unknown_environment_is_still_rejected(project):
    (project / ".env").write_text("TEST_ENV=prod\n")
    with pytest.raises(MissingSettingError, match="unknown TEST_ENV 'prod'"):
        get_settings()
