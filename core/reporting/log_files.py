"""Daily application log file naming and retention."""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path

from core.settings import ROOT

LOG_DIR = ROOT / "reports" / "logs"
PREFIX = "application-"


def daily_log_path(day: date | None = None) -> Path:
    return LOG_DIR / f"{PREFIX}{(day or date.today()).isoformat()}.log"


def purge_old_logs(retention_days: int, log_dir: Path = LOG_DIR) -> list[Path]:
    """Delete application logs not modified for more than retention_days (0 disables)."""
    if retention_days <= 0 or not log_dir.exists():
        return []
    cutoff = time.time() - retention_days * 86400
    removed = []
    for path in log_dir.glob(f"{PREFIX}*.log"):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed.append(path)
    return removed
