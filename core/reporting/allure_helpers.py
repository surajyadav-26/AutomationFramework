"""Thin wrappers over allure attachments and the environment.properties writer."""

from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import allure
from allure_commons.types import AttachmentType


def attach_png(data: bytes, name: str) -> None:
    allure.attach(data, name=name, attachment_type=AttachmentType.PNG)


def attach_json(data: object, name: str) -> None:
    allure.attach(
        json.dumps(data, indent=2, default=str), name=name, attachment_type=AttachmentType.JSON
    )


def attach_text(text: str, name: str) -> None:
    allure.attach(text, name=name, attachment_type=AttachmentType.TEXT)


def write_environment_properties(results_dir: Path, properties: dict[str, str]) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    base = {"python": platform.python_version(), "os": f"{platform.system()} {platform.release()}"}
    base["interpreter"] = sys.executable.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
    lines = [f"{k}={v}" for k, v in {**base, **properties}.items()]
    target = results_dir / "environment.properties"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
