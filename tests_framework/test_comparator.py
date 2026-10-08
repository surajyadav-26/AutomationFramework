"""core.visual.comparator and masking."""

import io

import pytest
from PIL import Image, ImageDraw

from core.visual.comparator import MAX_DIFF_RATIO, PIXEL_TOLERANCE, compare
from core.visual.masking import paint_regions

SIZE = (200, 100)


def png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def base() -> Image.Image:
    return Image.new("RGB", SIZE, (240, 240, 240))


def test_identical_images_match(base):
    result = compare(png(base), png(base))
    assert result.matches
    assert result.diff_ratio == 0
    assert result.reason == ""


def test_large_change_is_detected_with_diff_image(base):
    changed = base.copy()
    ImageDraw.Draw(changed).rectangle((20, 20, 120, 70), fill=(200, 0, 0))
    result = compare(png(changed), png(base))
    assert not result.matches
    assert result.diff_ratio > MAX_DIFF_RATIO
    assert result.diff_image is not None
    assert "pixels differ" in result.reason


def test_difference_within_per_pixel_tolerance_is_ignored(base):
    shade = tuple(c - PIXEL_TOLERANCE for c in (240, 240, 240))
    changed = Image.new("RGB", SIZE, shade)
    assert compare(png(changed), png(base)).matches


def test_difference_just_over_tolerance_is_detected(base):
    shade = tuple(c - PIXEL_TOLERANCE - 1 for c in (240, 240, 240))
    changed = Image.new("RGB", SIZE, shade)
    assert not compare(png(changed), png(base)).matches


def test_few_changed_pixels_stay_under_the_ratio_limit(base):
    changed = base.copy()
    changed.putpixel((5, 5), (0, 0, 0))  # 1 of 20000 pixels = 0.005%
    result = compare(png(changed), png(base))
    assert result.matches
    assert 0 < result.diff_ratio < MAX_DIFF_RATIO


def test_ratio_limit_is_configurable(base):
    changed = base.copy()
    ImageDraw.Draw(changed).rectangle((0, 0, 9, 9), fill=(0, 0, 0))  # 0.5%
    assert not compare(png(changed), png(base)).matches
    assert compare(png(changed), png(base), max_ratio=0.01).matches


def test_size_mismatch_fails_without_diff_image(base):
    result = compare(png(base.resize((100, 50))), png(base))
    assert not result.matches
    assert result.diff_image is None
    assert "size mismatch" in result.reason


def test_masked_region_hides_the_difference(base):
    changed = base.copy()
    ImageDraw.Draw(changed).rectangle((20, 20, 120, 70), fill=(200, 0, 0))
    assert not compare(png(changed), png(base)).matches
    assert compare(png(changed), png(base), regions=[(20, 20, 120, 70)]).matches


def test_difference_outside_the_mask_still_fails(base):
    changed = base.copy()
    ImageDraw.Draw(changed).rectangle((150, 10, 190, 90), fill=(200, 0, 0))
    assert not compare(png(changed), png(base), regions=[(0, 0, 50, 50)]).matches


def test_paint_regions_returns_a_copy_and_blacks_out_the_area(base):
    painted = paint_regions(base, [(10, 10, 20, 20)])
    assert painted.getpixel((15, 15)) == (0, 0, 0)
    assert base.getpixel((15, 15)) == (240, 240, 240)
    assert painted.getpixel((50, 50)) == (240, 240, 240)
