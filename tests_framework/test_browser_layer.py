"""BasePage and the axe scanner against a real Chromium, using local HTML only (no network)."""

import io

import pytest
from PIL import Image

from core.accessibility.axe_scanner import scan
from core.browser.base_page import BasePage
from core.visual.comparator import compare

ROW = """
<html><body style="margin:0;font:20px monospace">
  <div style="display:flex;justify-content:space-between;width:400px;padding:10px">
    <div data-test="price">{price}</div><button>Add to cart</button>
  </div>
</body></html>
"""
CLEAN = (
    '<html lang="en"><head><title>t</title></head><body><main><h1>Hello</h1>'
    '<button>Save</button><label for="n">Name</label><input id="n"></main></body></html>'
)
BROKEN = (
    '<html lang="en"><head><title>t</title></head><body><main>'
    '<img src="x.png"><button></button></main></body></html>'
)


@pytest.fixture(autouse=True)
def data_test_attribute(playwright):
    """The framework's root conftest does this for the real suites."""
    playwright.selectors.set_test_id_attribute("data-test")


@pytest.fixture
def base_page(page):
    return BasePage(page, "https://app.example")


def shot(base_page, html, **options):
    base_page.page.set_content(html)
    return base_page.screenshot(**options)


def test_by_test_finds_the_data_test_attribute(base_page):
    base_page.page.set_content(
        '<div data-test="greeting">hi</div><div data-testid="other">no</div>'
    )
    assert base_page.by_test("greeting").inner_text() == "hi"
    assert base_page.by_test("other").count() == 0


def test_resize_changes_the_viewport(base_page):
    base_page.resize(375, 667)
    assert base_page.page.viewport_size == {"width": 375, "height": 667}


def test_open_joins_base_url_and_path_and_expect_url_contains_checks_it(page):
    page.route(
        "**/inventory.html",
        lambda route: route.fulfill(body="<p>ok</p>", content_type="text/html"),
    )

    class Inventory(BasePage):
        path = "/inventory.html"

    inventory = Inventory(page, "http://app.example/")
    inventory.open()
    inventory.expect_url_contains("/inventory.html")
    assert page.url == "http://app.example/inventory.html"
    with pytest.raises(AssertionError):
        inventory.expect_url_contains("/cart.html")


def test_hiding_text_keeps_the_layout_so_different_prices_look_identical(base_page):
    hide = ['[data-test="price"]']
    cheap = shot(base_page, ROW.format(price="$9.99"), hide=hide)
    expensive = shot(base_page, ROW.format(price="$1,299.99"), hide=hide)
    assert compare(cheap, expensive, max_ratio=0).matches


def test_without_hiding_different_prices_do_differ(base_page):
    cheap = shot(base_page, ROW.format(price="$9.99"))
    expensive = shot(base_page, ROW.format(price="$1,299.99"))
    # the change is tiny (about 0.05% of the page), so only a zero-tolerance compare sees it
    assert not compare(cheap, expensive, max_ratio=0).matches


def test_hiding_keeps_neighbouring_elements_in_the_picture(base_page):
    hidden = shot(base_page, ROW.format(price="$9.99"), hide=['[data-test="price"]'])
    no_button = shot(
        base_page, ROW.format(price="$9.99").replace("<button>Add to cart</button>", "")
    )
    assert not compare(hidden, no_button).matches  # the button is still there in `hidden`


def test_masking_paints_a_solid_box_over_the_element(base_page):
    base_page.page.set_content(ROW.format(price="$9.99"))
    png = base_page.screenshot(mask=[base_page.by_test("price")])
    pixels = Image.open(io.BytesIO(png)).convert("RGB").getcolors(maxcolors=1_000_000)
    assert (255, 0, 255) in {color for _, color in pixels}  # Playwright's default mask colour


def test_animations_do_not_make_screenshots_flaky(base_page):
    animated = (
        "<style>@keyframes blink {from {background:red} to {background:blue}}"
        "div {width:100px;height:100px;animation:blink 0.2s infinite alternate}</style><div></div>"
    )
    first = shot(base_page, animated)
    base_page.page.wait_for_timeout(137)
    second = base_page.screenshot()
    assert compare(first, second, max_ratio=0).matches


def test_screenshot_waits_for_images_to_finish_loading(base_page):
    base_page.page.route(
        "**/slow.png",
        lambda route: (base_page.page.wait_for_timeout(300), route.fulfill(status=404, body=b"")),
    )
    base_page.page.set_content('<img src="https://app.example/slow.png" width="50" height="50">')
    base_page.screenshot()
    assert base_page.page.evaluate("Array.from(document.images).every(i => i.complete)")


# --- real axe engine ----------------------------------------------------------------------------


def test_axe_finds_real_wcag_violations(base_page):
    base_page.page.set_content(BROKEN)
    found = {violation["id"]: violation["impact"] for violation in scan(base_page.page)}
    assert found["image-alt"] == "critical"
    assert found["button-name"] == "critical"


def test_axe_reports_nothing_for_an_accessible_page(base_page):
    base_page.page.set_content(CLEAN)
    assert scan(base_page.page) == []


def test_best_practice_rules_only_appear_when_asked_for(base_page):
    base_page.page.set_content(
        "<html lang='en'><head><title>t</title></head><body><p>x</p></body></html>"
    )
    default_rules = {v["id"] for v in scan(base_page.page)}
    extended_rules = {v["id"] for v in scan(base_page.page, include_best_practices=True)}
    assert "region" not in default_rules
    assert "region" in extended_rules
