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


# --- the browser plugin's fixtures (called directly: the real sessions use them end to end) -------


def test_the_browser_context_is_fixed_for_deterministic_screenshots():
    from core.browser import plugin
    from core.settings import LOCALE, TIMEZONE, VIEWPORT

    build = plugin.browser_context_args._get_wrapped_function()
    context = build({"ignore_https_errors": True})
    assert context["viewport"] == VIEWPORT
    assert context["viewport"] is not VIEWPORT  # a copy: nobody can change the constant
    assert (context["locale"], context["timezone_id"]) == (LOCALE, TIMEZONE)
    assert context["reduced_motion"] == "reduce"
    assert context["ignore_https_errors"] is True  # what pytest-playwright already set is kept


def test_the_test_id_attribute_is_set_to_data_test():
    from core.browser import plugin

    class FakePlaywright:
        def __init__(self):
            self.attributes = []
            self.selectors = self

        def set_test_id_attribute(self, name):
            self.attributes.append(name)

    fake = FakePlaywright()
    assert plugin.playwright._get_wrapped_function()(fake) is fake
    assert fake.attributes == ["data-test"]


# --- components: scoped to their own root ----------------------------------------------

HEADER_HTML = (
    '<header data-test="primary-header"><button>Open Menu</button><span>Swag Labs</span>'
    '<a data-test="shopping-cart-link" href="#">cart</a></header><main>content</main>'
)


def test_a_component_finds_things_only_inside_its_own_root(page):
    from core.browser.base_component import BaseComponent

    page.set_content(
        '<section data-test="first"><i data-test="item">one</i></section>'
        '<section data-test="second"><i data-test="item">two</i></section>'
    )
    second = BaseComponent(page.get_by_test_id("second"))
    assert second.by_test("item").inner_text() == "two"
    assert second.by_test("item").count() == 1  # not the other section's item as well


def test_a_component_reports_when_its_root_is_not_visible(page):
    from core.browser.base_component import BaseComponent

    page.set_content('<div data-test="box" style="display:none">x</div>')
    page.set_default_timeout(500)
    with pytest.raises(AssertionError):
        BaseComponent(page.get_by_test_id("box")).expect_visible()


def test_the_header_component_is_loaded_when_logo_menu_and_cart_are_there(page):
    from pages.components.header import Header

    page.set_content(HEADER_HTML)
    Header(page).expect_loaded()


@pytest.mark.parametrize(
    "broken",
    [
        HEADER_HTML.replace("Swag Labs", "Other Brand"),
        HEADER_HTML.replace("Open Menu", "Menu"),
        HEADER_HTML.replace('data-test="shopping-cart-link"', 'data-test="other"'),
    ],
    ids=["wrong logo", "no menu button", "no cart link"],
)
def test_the_header_component_notices_each_missing_part(page, broken):
    from pages.components.header import Header

    page.set_content(broken)
    page.set_default_timeout(500)
    with pytest.raises(AssertionError):
        Header(page).expect_loaded()
