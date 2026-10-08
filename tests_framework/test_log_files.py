"""core.reporting.log_files naming and retention."""

import os
import time
from datetime import date

from core.reporting.log_files import daily_log_path, purge_old_logs


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
