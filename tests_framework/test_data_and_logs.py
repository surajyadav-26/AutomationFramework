"""Test data helpers (cleanup registry, factories) and the daily log files."""

import json
import os
import time
from datetime import date
from types import SimpleNamespace

import pytest

from core.data import factories
from core.data.cleanup import Cleanup
from core.data.factories import random_password, unique
from core.reporting.log_files import daily_log_path, purge_old_logs


def test_callbacks_run_in_reverse_order():
    order = []
    cleanup = Cleanup()
    cleanup.register(lambda: order.append("first"))
    cleanup.register(lambda: order.append("second"))
    assert cleanup.run_all() == []
    assert order == ["second", "first"]


def test_a_failing_callback_does_not_stop_the_others_and_is_reported():
    ran = []

    def boom():
        raise RuntimeError("nope")

    cleanup = Cleanup()
    cleanup.register(lambda: ran.append("a"), "a")
    cleanup.register(boom, "boom")
    cleanup.register(lambda: ran.append("c"), "c")
    assert cleanup.run_all() == ["boom"]
    assert ran == ["c", "a"]


def test_registry_is_empty_after_running():
    calls = []
    cleanup = Cleanup()
    cleanup.register(lambda: calls.append(1))
    cleanup.run_all()
    cleanup.run_all()
    assert calls == [1]


def test_unique_values_do_not_repeat_and_keep_the_prefix():
    values = {unique("user") for _ in range(200)}
    assert len(values) == 200
    assert all(v.startswith("user-") for v in values)


def test_random_passwords_are_unique():
    assert random_password() != random_password()


# --- daily log files and retention -----------------------------------------------------------


def make(path, age_days):
    path.write_text("x")
    stamp = time.time() - age_days * 86400
    os.utime(path, (stamp, stamp))
    return path


def test_daily_log_name():
    assert daily_log_path(date(2026, 10, 8)).name == "application-2026-10-08.log"
    assert daily_log_path().parent.name == "logs"


def test_purge_removes_only_old_application_logs(tmp_path):
    old = make(tmp_path / "application-2026-09-01.log", 10)
    fresh = make(tmp_path / "application-2026-10-07.log", 1)
    other = make(tmp_path / "other.log", 100)
    removed = purge_old_logs(7, tmp_path)
    assert removed == [old]
    assert not old.exists()
    assert fresh.exists()
    assert other.exists()


def test_file_inside_the_window_is_kept(tmp_path):
    kept = make(tmp_path / "application-a.log", 6)
    assert purge_old_logs(7, tmp_path) == []
    assert kept.exists()


def test_zero_or_negative_retention_keeps_everything(tmp_path):
    old = make(tmp_path / "application-a.log", 500)
    assert purge_old_logs(0, tmp_path) == []
    assert purge_old_logs(-3, tmp_path) == []
    assert old.exists()


def test_missing_folder_is_not_an_error(tmp_path):
    assert purge_old_logs(7, tmp_path / "nope") == []


# --- users per environment ---------------------------------------------------------------------


@pytest.fixture
def user_files(tmp_path, monkeypatch):
    (tmp_path / "users.json").write_text(json.dumps({"admin": "admin_user", "guest": "guest_user"}))
    environment = SimpleNamespace(env="qa")
    monkeypatch.setattr(factories, "TEST_DATA", tmp_path)
    monkeypatch.setattr(factories, "get_settings", lambda: environment)
    factories._users.cache_clear()
    yield SimpleNamespace(folder=tmp_path, environment=environment)
    factories._users.cache_clear()


def test_the_shared_users_file_is_used_when_the_environment_has_no_file(user_files):
    assert factories.username_for("admin") == "admin_user"


def test_an_environment_file_replaces_only_the_roles_it_lists(user_files):
    (user_files.folder / "users.uat.json").write_text(json.dumps({"admin": "uat_admin"}))
    user_files.environment.env = "uat"
    assert factories.username_for("admin") == "uat_admin"
    assert factories.username_for("guest") == "guest_user"


def test_another_environments_file_is_ignored(user_files):
    (user_files.folder / "users.uat.json").write_text(json.dumps({"admin": "uat_admin"}))
    assert factories.username_for("admin") == "admin_user"  # the environment is qa


def test_an_environment_file_can_add_roles(user_files):
    (user_files.folder / "users.qa.json").write_text(json.dumps({"auditor": "qa_auditor"}))
    assert factories.username_for("auditor") == "qa_auditor"
    with pytest.raises(KeyError, match="known: \['admin', 'auditor', 'guest'\]"):
        factories.username_for("nobody")
