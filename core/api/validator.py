"""JSON schema validation."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from core.settings import ROOT

SCHEMA_DIR = ROOT / "test_data" / "schemas"


def validate_schema(instance: object, schema_name: str) -> None:
    """Raise AssertionError listing every violation of test_data/schemas/<schema_name>."""
    schema = json.loads(Path(SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors
        )
        raise AssertionError(f"schema {schema_name} violated: {details}")
