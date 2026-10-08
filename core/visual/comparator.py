"""Pillow pixel diff between an actual screenshot and a baseline."""

from __future__ import annotations

import io
from collections.abc import Iterable
from dataclasses import dataclass

from PIL import Image, ImageChops

from core.visual.masking import Region, paint_regions

MAX_DIFF_RATIO = 0.001  # 0.1% of pixels
PIXEL_TOLERANCE = 10  # max per-channel difference still considered equal


@dataclass
class Comparison:
    matches: bool
    diff_ratio: float
    diff_image: bytes | None
    reason: str = ""


def _load(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def compare(
    actual: bytes,
    baseline: bytes,
    regions: Iterable[Region] = (),
    max_ratio: float = MAX_DIFF_RATIO,
    tolerance: int = PIXEL_TOLERANCE,
) -> Comparison:
    img_a, img_b = _load(actual), _load(baseline)
    if img_a.size != img_b.size:
        return Comparison(
            False, 1.0, None, f"size mismatch: actual {img_a.size} vs baseline {img_b.size}"
        )
    regions = list(regions)
    if regions:
        img_a, img_b = paint_regions(img_a, regions), paint_regions(img_b, regions)

    diff = ImageChops.difference(img_a, img_b)
    r, g, b = diff.split()
    worst = ImageChops.lighter(ImageChops.lighter(r, g), b)
    changed = worst.point(lambda v: 255 if v > tolerance else 0)
    ratio = changed.histogram()[255] / (img_a.width * img_a.height)

    overlay = Image.new("RGB", img_a.size, (255, 0, 0))
    highlighted = Image.composite(
        overlay, Image.blend(img_a, Image.new("RGB", img_a.size, "white"), 0.7), changed
    )
    ok = ratio <= max_ratio
    reason = "" if ok else f"{ratio:.4%} of pixels differ (limit {max_ratio:.2%})"
    return Comparison(ok, ratio, _png(highlighted), reason)
