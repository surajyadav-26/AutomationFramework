"""Secrets handling and configuration hygiene: redaction, URL validation, leak scan, doc drift."""

import importlib.util
import re
from pathlib import Path

import pytest

from core import settings as settings_module
from core.api import http_client
from core.api.http_client import HttpClient
from core.api.redaction import MASK, redact
from core.settings import MissingSettingError, get_settings

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_rules", ROOT / "tools" / "check_rules.py")
check_rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_rules)


# --- redaction -----------------------------------------------------------------------------------


def test_sensitive_keys_are_masked_at_any_depth_and_case():
    data = {
        "username": "emilys",
        "password": "hunter2",
        "Authorization": "Bearer abc",
        "nested": {"accessToken": "t", "refresh_token": "r", "items": [{"apiKey": "k", "ok": 1}]},
        "Set-Cookie": "sid=1",
    }
    assert redact(data) == {
        "username": "emilys",
        "password": MASK,
        "Authorization": MASK,
        "nested": {
            "accessToken": MASK,
            "refresh_token": MASK,
            "items": [{"apiKey": MASK, "ok": 1}],
        },
        "Set-Cookie": MASK,
    }


def test_redaction_returns_a_copy_and_keeps_empty_values_visible():
    original = {"password": "x", "token": ""}
    result = redact(original)
    assert original == {"password": "x", "token": ""}
    assert result == {"password": MASK, "token": ""}


def test_non_sensitive_data_and_scalars_are_unchanged():
    assert redact({"id": 1, "tags": ["a", "b"]}) == {"id": 1, "tags": ["a", "b"]}
    assert redact("text") == "text"
    assert redact(None) is None


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {"Authorization": "Bearer top-secret"}

    def request(self, method, url, **kwargs):
        return self.response


def test_the_http_client_never_attaches_credentials(monkeypatch):
    import requests

    response = requests.Response()
    response.status_code = 200
    response._content = b'{"accessToken": "tok-123", "refreshToken": "ref-456", "id": 1}'
    attachments = []
    monkeypatch.setattr(http_client, "attach_json", lambda data, name: attachments.append(data))
    client = HttpClient("https://api.example")
    client.session = FakeSession(response)
    client.post(
        "/auth/login", json={"username": "u", "password": "pw-789"}, headers={"X-Api-Key": "k"}
    )
    dump = repr(attachments)
    for secret in ("pw-789", "tok-123", "ref-456", "top-secret", "'k'"):
        assert secret not in dump
    assert dump.count(MASK) >= 5
    assert "'id': 1" in dump  # useful, non-sensitive data is still reported


# --- URL validation ------------------------------------------------------------------------------


@pytest.fixture
def env(monkeypatch):
    monkeypatch.delenv("ATTACH_TRACE_AND_VIDEO", raising=False)
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(settings_module, "dotenv_values", lambda *a, **k: {})
    monkeypatch.setenv("APP_URL", "https://app.example")
    monkeypatch.setenv("API_URL", "https://api.example")
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


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


# --- leak scan -----------------------------------------------------------------------------------


def write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture(autouse=True)
def no_ambient_secrets(monkeypatch):
    for name in ("APP_PASSWORD", "API_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    "line",
    [
        'API_TOKEN = "abcd1234"',
        "APP_PASSWORD=sup3rsecret",
        "DB_SECRET: hunter22",
        "SECRET_KEY='abcdef'",
    ],
)
def test_assigned_secret_literals_are_reported(tmp_path, line):
    write(tmp_path, "docs/a.md", line + "\n")
    assert len(check_rules.check_secrets(tmp_path)) == 1


@pytest.mark.parametrize(
    "line",
    [
        "APP_PASSWORD=",
        'OK_PASSWORD = os.getenv("X")',
        "SECRET: ${{ secrets.X }}",
        'APP_PASSWORD="$APP_PASSWORD"',
        "API_PASSWORD=<your password>",
        '"accessToken": {"type": "string"}',
        "password = request.password",
    ],
)
def test_placeholders_calls_and_lowercase_names_are_not_reported(tmp_path, line):
    write(tmp_path, "docs/a.md", line + "\n")
    assert check_rules.check_secrets(tmp_path) == []


def test_the_real_value_of_a_secret_setting_is_found_anywhere(tmp_path):
    write(tmp_path, ".env", "APP_PASSWORD=value-from-env-file\n")
    write(tmp_path, "docs/notes.md", "temporary: value-from-env-file\n")
    errors = check_rules.check_secrets(tmp_path)
    assert errors == ["docs\\notes.md:1: contains the value of a secret setting"] or errors == [
        "docs/notes.md:1: contains the value of a secret setting"
    ]


def test_the_real_value_from_the_environment_is_found_too(tmp_path, monkeypatch):
    monkeypatch.setenv("API_PASSWORD", "env-only-value")
    write(tmp_path, "steps/x.py", "x = 'env-only-value'\n")
    assert len(check_rules.check_secrets(tmp_path)) == 1


def test_local_secret_files_and_generated_folders_are_not_scanned(tmp_path):
    write(tmp_path, ".env", "APP_PASSWORD=abcd1234\n")
    write(tmp_path, ".env.stage", "APP_PASSWORD=abcd1234\n")
    write(tmp_path, "reports/x.txt", "APP_PASSWORD=abcd1234\n")
    write(tmp_path, "logs/x.log", "APP_PASSWORD=abcd1234\n")
    assert check_rules.check_secrets(tmp_path) == []


def test_binary_files_are_skipped(tmp_path):
    (tmp_path / "image.png").write_bytes(bytes(range(256)) * 10)
    assert check_rules.check_secrets(tmp_path) == []


def test_the_real_repository_has_no_leaked_secrets():
    assert check_rules.check_secrets(ROOT) == []


# --- documentation drift ---------------------------------------------------------------------


def setting_names():
    source = (ROOT / "core" / "settings.py").read_text(encoding="utf-8")
    names = set(
        re.findall(r'_(?:choice|int|float|bool|require|require_url)\("([A-Z0-9_]+)"', source)
    )
    names |= set(re.findall(r'getenv\("([A-Z0-9_]+)"', source))
    return names - {"CI"}  # CI is set by the CI system, never by us


def test_every_setting_is_documented_in_the_readme():
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    missing = sorted(name for name in setting_names() if name not in readme)
    assert missing == [], f"add these settings to docs/README.md: {missing}"


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
