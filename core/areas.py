"""Feature areas (auth, cart, ...): one folder name that ties features, steps, pages and baselines.

The area is the folder directly under a suite: features/<suite>/<area>/, steps/<suite>/<area>/,
pages/<area>/, clients/<area>/ and baselines/<os>/<browser>/<WxH>/<area>/. Nothing types it twice:
it is read from the path of the running test.
"""

from __future__ import annotations

from pathlib import Path

SUITES = ("ui", "api", "visual", "accessibility")
RESERVED = {
    *SUITES,
    "smoke",
    "shared",
    "components",
}  # cannot be area names (they are markers/folders)


def area_of(path: Path) -> str | None:
    """steps/<suite>/<area>/test_x.py -> <area>; None when the path does not follow the layout."""
    parts = path.parts
    if "steps" not in parts:
        return None
    index = len(parts) - 1 - parts[::-1].index("steps")
    below = parts[index + 1 :]  # <suite>, <area>, <file>
    if len(below) >= 3 and below[0] in SUITES:
        return below[1]
    return None


def discover_areas(root: Path) -> list[str]:
    """Every folder name found under features/<suite>/, sorted."""
    features = root / "features"
    if not features.exists():
        return []
    return sorted(
        {p.name for p in features.glob("*/*") if p.is_dir() and not p.name.startswith("_")}
    )


def is_valid_area_name(name: str) -> bool:
    """A lower-case identifier that is not a reserved word."""
    return (
        name.isidentifier()
        and name == name.lower()
        and not name.startswith("_")
        and name not in RESERVED
    )
