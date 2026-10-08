"""Test data helpers (cleanup registry, factories) and the daily log files."""

import os
import time
from datetime import date

import pytest

from core.data.cleanup import Cleanup
from core.data.factories import random_password, unique, username_for
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


def test_known_roles_resolve_and_unknown_roles_fail_clearly():
    assert username_for("standard") == "standard_user"
    assert username_for("no_username") == ""
    with pytest.raises(KeyError, match="unknown user role 'ghost'"):
        username_for("ghost")


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
