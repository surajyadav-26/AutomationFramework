"""Masking of volatile areas, either as page locators or as fixed pixel regions."""

from __future__ import annotations

from collections.abc import Iterable

from PIL import Image, ImageDraw

Region = tuple[int, int, int, int]  # left, top, right, bottom


def locators_for(page, selectors: Iterable[str]) -> list:
    """Locators to hand to Playwright's screenshot(mask=...)."""
    return [page.locator(selector) for selector in selectors]


def paint_regions(image: Image.Image, regions: Iterable[Region]) -> Image.Image:
    """Return a copy of image with each region filled solid black."""
    masked = image.copy()
    draw = ImageDraw.Draw(masked)
    for region in regions:
        draw.rectangle(region, fill=(0, 0, 0))
    return masked
