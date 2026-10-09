"""Resolves baseline paths: baselines/<os>/<browser>/<WxH>/<area>/<name>.png."""

from __future__ import annotations

import platform
from collections.abc import Mapping
from pathlib import Path

from core.settings import ROOT

BASELINE_DIR = ROOT / "baselines"
_OS_NAMES = {"Linux": "linux", "Windows": "windows", "Darwin": "macos"}


def os_name() -> str:
    system = platform.system()
    if system not in _OS_NAMES:
        raise RuntimeError(f"unsupported OS for visual baselines: {system}")
    return _OS_NAMES[system]


def baseline_path(name: str, browser: str, viewport: Mapping[str, object], area: str = "") -> Path:
    """The area (auth, cart, ...) keeps the images of different features apart."""
    size = f"{viewport['width']}x{viewport['height']}"
    return BASELINE_DIR / os_name() / browser / size / area / f"{name}.png"


def save(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
