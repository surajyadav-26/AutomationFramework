"""Visual comparison: pixel diff, masking, baseline paths, anti-aliasing, hide-in-place CSS."""

import io
import platform

import pytest
from PIL import Image, ImageDraw

from core.browser.base_page import BasePage, hide_css
from core.visual import baseline_store
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


# --- baseline paths -------------------------------------------------------------------------


VIEWPORT = {"width": 1280, "height": 720}


@pytest.mark.parametrize(
    ("system", "folder"), [("Linux", "linux"), ("Windows", "windows"), ("Darwin", "macos")]
)
def test_os_name_maps_platform(monkeypatch, system, folder):
    monkeypatch.setattr(platform, "system", lambda: system)
    assert baseline_store.os_name() == folder


def test_unsupported_os_raises(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Plan9")
    with pytest.raises(RuntimeError, match="unsupported OS"):
        baseline_store.os_name()


def test_baseline_path_is_keyed_by_os_browser_and_viewport(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    path = baseline_store.baseline_path("login_page", "firefox", VIEWPORT)
    expected = baseline_store.BASELINE_DIR / "linux" / "firefox" / "1280x720" / "login_page.png"
    assert path == expected


def test_different_browsers_and_viewports_never_share_a_path(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    paths = {
        baseline_store.baseline_path("p", "chromium", VIEWPORT),
        baseline_store.baseline_path("p", "firefox", VIEWPORT),
        baseline_store.baseline_path("p", "chromium", {"width": 375, "height": 667}),
    }
    assert len(paths) == 3


def test_save_creates_missing_folders(tmp_path):
    target = tmp_path / "linux" / "chromium" / "1280x720" / "x.png"
    baseline_store.save(target, b"data")
    assert target.read_bytes() == b"data"


# --- anti-aliasing tolerance ----------------------------------------------------------------


def thin_line_variant(base):
    """A 1px wide line across the page: the shape of an anti-aliasing / edge difference."""
    changed = base.copy()
    ImageDraw.Draw(changed).line((0, 50, 199, 50), fill=(0, 0, 0), width=1)
    return changed  # 200 of 20000 pixels = 1%


def test_thin_differences_fail_by_default(base):
    assert not compare(png(thin_line_variant(base)), png(base)).matches


def test_thin_differences_are_ignored_when_antialiasing_is_ignored(base):
    result = compare(png(thin_line_variant(base)), png(base), ignore_antialiasing=True)
    assert result.matches
    assert result.diff_ratio == 0


def test_isolated_pixels_are_ignored_when_antialiasing_is_ignored(base):
    changed = base.copy()
    for x in range(0, 200, 4):
        changed.putpixel((x, 10), (0, 0, 0))
    assert compare(png(changed), png(base), ignore_antialiasing=True).matches


def test_a_real_block_change_still_fails_with_antialiasing_ignored(base):
    changed = base.copy()
    ImageDraw.Draw(changed).rectangle((20, 20, 120, 70), fill=(200, 0, 0))
    result = compare(png(changed), png(base), ignore_antialiasing=True)
    assert not result.matches
    assert result.diff_ratio > 0.1


# --- hide in place (with a fake page; test_browser_layer.py uses a real browser) ---------------


def test_hide_css_keeps_layout_and_covers_every_selector():
    css = hide_css(['[data-test="price"]', ".badge"])
    assert css.count("visibility: hidden !important") == 2
    assert '[data-test="price"]' in css
    assert ".badge" in css
    assert "display" not in css  # display:none would shift the layout
    assert hide_css([]) == ""


class FakePage:
    def __init__(self):
        self.calls = []

    def add_style_tag(self, content):
        self.calls.append(("style_tag", content))

    def wait_for_load_state(self, state):
        self.calls.append(("wait", state))

    def evaluate(self, script):
        self.calls.append(("evaluate", script))

    def wait_for_function(self, script):
        self.calls.append(("wait_for_function", script))

    def screenshot(self, **kwargs):
        self.calls.append(("screenshot", kwargs))
        return b"png"

    def set_viewport_size(self, size):
        self.calls.append(("viewport", size))

    def goto(self, url):
        self.calls.append(("goto", url))


def test_screenshot_passes_hide_css_and_stabilising_options():
    page = FakePage()
    result = BasePage(page, "https://x.example").screenshot(hide=[".price"])
    assert result == b"png"
    options = dict(page.calls)["screenshot"]
    assert "visibility: hidden" in options["style"]
    assert options["animations"] == "disabled"
    assert options["caret"] == "hide"
    assert options["mask"] == []


def test_screenshot_waits_for_fonts_and_images_not_for_network_idle():
    page = FakePage()
    BasePage(page, "https://x.example").screenshot()
    waits = [call for call in page.calls if call[0] in ("wait", "evaluate", "wait_for_function")]
    assert ("wait", "load") in waits
    assert any("fonts.ready" in str(call[1]) for call in waits)
    assert any("document.images" in str(call[1]) for call in waits)
    assert ("wait", "networkidle") not in waits
    assert [call[0] for call in page.calls].index("screenshot") > max(
        i
        for i, call in enumerate(page.calls)
        if call[0] in ("wait", "evaluate", "wait_for_function")
    )


def test_screenshot_without_hide_sends_no_style():
    page = FakePage()
    BasePage(page, "https://x.example").screenshot()
    assert dict(page.calls)["screenshot"]["style"] is None


def test_resize_sets_the_viewport():
    page = FakePage()
    BasePage(page, "https://x.example").resize(375, 667)
    assert ("viewport", {"width": 375, "height": 667}) in page.calls


def test_open_joins_base_url_and_path_once():
    page = FakePage()

    class Inventory(BasePage):
        path = "/inventory.html"

    Inventory(page, "https://x.example/").open()
    assert ("goto", "https://x.example/inventory.html") in page.calls
