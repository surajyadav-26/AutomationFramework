"""Generate the Allure HTML report and open it in the browser."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

THEME_SCRIPT = (
    "<script>try{if(!localStorage.getItem('allure-theme'))"
    "localStorage.setItem('allure-theme','%s')}catch(e){}</script>"
)


def apply_theme(report_dir: Path, theme: str) -> None:
    """Make the report start in the given theme unless the viewer already picked one."""
    index = report_dir / "index.html"
    html = index.read_text(encoding="utf-8")
    index.write_text(html.replace("<head>", "<head>" + THEME_SCRIPT % theme, 1), encoding="utf-8")


def generate_and_open(results_dir: Path, report_dir: Path, theme: str) -> str:
    """Build the report and open it. Returns a one-line status message."""
    allure = shutil.which("allure")
    if not allure:
        return "allure CLI not found on PATH; report not generated (set ALLURE_AUTO_OPEN=false)"
    if not results_dir.exists() or not any(results_dir.glob("*-result.json")):
        return "no allure results; report not generated"
    done = subprocess.run(
        [allure, "generate", str(results_dir), "-o", str(report_dir), "--clean"],
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        return f"allure generate failed: {done.stderr.strip() or done.stdout.strip()}"
    apply_theme(report_dir, theme)
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    # `allure open` serves the report until stopped, so it must outlive pytest; no console window
    subprocess.Popen(
        [allure, "open", str(report_dir)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    return f"allure report opened ({report_dir})"
