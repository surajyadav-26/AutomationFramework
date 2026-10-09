"""Base class for page components: reusable parts of a page (header, modal, table ...).

A component is found inside one root locator, so two identical widgets on a page never get mixed up
and every locator it offers is scoped to its own root.
"""

from __future__ import annotations

import logging

from playwright.sync_api import Locator, expect


class BaseComponent:
    def __init__(self, root: Locator):
        self.root = root
        self.log = logging.getLogger(f"ui.{type(self).__name__}")

    def by_test(self, test_id: str) -> Locator:
        """Locator by test id, searched inside this component only."""
        return self.root.get_by_test_id(test_id)

    def expect_visible(self) -> None:
        self.log.info("expect visible")
        expect(self.root).to_be_visible()
