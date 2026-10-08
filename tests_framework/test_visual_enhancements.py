"""Anti-aliasing tolerance, hide-in-place CSS, viewport resize and the new settings key."""

import io

import pytest
from PIL import Image, ImageDraw

from core import settings as settings_module
from core.browser.base_page import BasePage, hide_css
from core.settings import MissingSettingError, get_settings
from core.visual.comparator import compare


def png(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def base():
    return Image.new("RGB", (200, 100), (240, 240, 240))


# --- anti-aliasing tolerance -------------------------------------------------------------------


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


# --- hide in place -------------------------------------------------------------------------------


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


# --- setting -------------------------------------------------------------------------------------


@pytest.fixture
def env(monkeypatch):
    monkeypatch.delenv("VISUAL_IGNORE_ANTIALIASING", raising=False)
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(settings_module, "dotenv_values", lambda *args, **kwargs: {})
    monkeypatch.setenv("APP_URL", "https://app.example")
    monkeypatch.setenv("API_URL", "https://api.example")
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def test_antialiasing_is_off_by_default(env):
    assert get_settings().visual_ignore_antialiasing is False


def test_antialiasing_can_be_enabled(env):
    env.setenv("VISUAL_IGNORE_ANTIALIASING", "true")
    assert get_settings().visual_ignore_antialiasing is True


def test_antialiasing_rejects_garbage(env):
    env.setenv("VISUAL_IGNORE_ANTIALIASING", "sometimes")
    with pytest.raises(MissingSettingError, match="VISUAL_IGNORE_ANTIALIASING"):
        get_settings()
