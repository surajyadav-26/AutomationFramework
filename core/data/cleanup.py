"""Registry of cleanup callbacks, run in reverse order at teardown even if the test failed."""

from __future__ import annotations

import logging
from collections.abc import Callable

log = logging.getLogger("cleanup")


class Cleanup:
    def __init__(self) -> None:
        self._callbacks: list[tuple[str, Callable[[], object]]] = []

    def register(self, callback: Callable[[], object], description: str = "") -> None:
        self._callbacks.append((description or getattr(callback, "__name__", "callback"), callback))

    def run_all(self) -> list[str]:
        """Run every callback (last registered first); return descriptions of those that raised."""
        failures = []
        while self._callbacks:
            description, callback = self._callbacks.pop()
            try:
                callback()
            except Exception:
                log.exception("cleanup failed: %s", description)
                failures.append(description)
        return failures
