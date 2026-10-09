# Contributing

1. Write or extend a `.feature` file under `features/<suite>/`. The first line tags the
   suite (`@ui`, `@api`, `@visual` or `@accessibility`); add `@smoke` to quick checks.
2. Reuse existing step wording from [VOCABULARY.md](VOCABULARY.md). Add new wording there too.
   Step text must be unique within a suite.
3. Put selectors in `pages/`, endpoints in `clients/`, shared plumbing in `core/`.
   Step files hold only Gherkin glue: no selectors, URLs or raw HTTP calls.
4. Respect the layering `steps -> pages/clients -> core`; `steps/api` never touches pages or
   Playwright; the browser suites (`ui`, `visual`, `accessibility`) never touch clients.
5. No hardcoded passwords. Use `settings.app_password` / `settings.api_password` and
   `core.data.factories.random_password()` for deliberately wrong ones.
6. Never skip, xfail or delete a failing test to pass a gate; fix the root cause.
7. Before pushing: `make check` (ruff, import rules, mypy, rules checker), `make test-framework` if you
   touched `core/` or `tools/`, and the suite you touched. New code gets type hints.
8. Visual changes: baselines are local and gitignored. After an intended change run
   `make update-baselines` and look at the new images before relying on them.
9. Do not hand-edit `reports/`, `baselines/` or `requirements.lock` (edit `requirements.in`, then
   regenerate the lock with `pip freeze` in a clean environment).

## Locator guidelines
The Playwright cheat sheet is at the end of this file.
- Prefer `get_by_role`, then `get_by_label`, then `get_by_text`: they describe what a user sees
  and double as a basic accessibility check.
- Use `get_by_test_id` (our `by_test()`, attribute `data-test`) when the page has no stable
  user-facing handle.
- Use CSS only for structure that nothing user-facing describes (for example the `.pricebar` container).
- Avoid long XPath chains and absolute paths such as `div > div > div:nth-child(3)`; they break
  when the layout changes. `tools/check_rules.py` fails on XPath, positional selectors,
  3+ level child chains and manual sleeps.
- Locators are lazy and auto-wait: do not add `time.sleep` or `wait_for_timeout`. Save a locator
  as a property or variable and reuse it (see `LoginPage.login_button`).
- Keep every locator in `pages/`, never in step files.

## Test data and cleanup (for stateful features)
Login-only tests create nothing, so none of them registers cleanup yet. When a scenario creates data:
```python
from core.data.factories import unique


@when("I create a customer", target_fixture="customer")
def _create(customer_client, cleanup):
    customer = customer_client.create(name=unique("cust"))  # unique values: no clashes in parallel
    cleanup.register(lambda: customer_client.delete(customer["id"]), "delete customer")
    return customer
```
The `cleanup` fixture (steps/conftest.py) runs the callbacks after the test, newest first, whether the
test passed or failed, and reports any callback that raised. tests_framework/test_steps_conftest.py
proves this with real pytest sessions. Pass data between steps with `target_fixture=`, not shared dicts.
Steps that two suites need go in `shared/login_steps.py`-style shared modules (star-imported, because
pytest-bdd registers a step in the module that defines it); browser fixtures are in
`shared/browser_fixtures.py`.

## Locator cheat sheet (Playwright, Python)

### 1. Quick pick guide
| I want to find... | Use |
|---|---|
| A button, link, heading, checkbox | `get_by_role()` |
| A form field by its label | `get_by_label()` |
| An input by placeholder | `get_by_placeholder()` |
| Any element by visible text | `get_by_text()` |
| An image | `get_by_alt_text()` |
| An element with a title tooltip | `get_by_title()` |
| An element with a stable test attribute | `get_by_test_id()` |
| Anything else (structure, CSS) | `locator()` |

### 2. Built-in locators (best to worst)
| # | Locator | Finds by | Example |
|---|---|---|---|
| 1 | `get_by_role()` | accessible role and name | `page.get_by_role("button", name="Login")` |
| 2 | `get_by_label()` | form field label | `page.get_by_label("Password")` |
| 3 | `get_by_placeholder()` | input placeholder | `page.get_by_placeholder("Username")` |
| 4 | `get_by_text()` | visible text | `page.get_by_text("Products")` |
| 5 | `get_by_alt_text()` | image alt | `page.get_by_alt_text("Sauce Labs Backpack")` |
| 6 | `get_by_title()` | title attribute | `page.get_by_title("Close")` |
| 7 | `get_by_test_id()` | test id attribute (`data-test` here) | `page.get_by_test_id("login-button")` |

`get_by_role` options:
```python
page.get_by_role("button", name="Login", exact=True)
page.get_by_role("checkbox", name="Remember me", checked=True)
page.get_by_role("heading", name="Products", level=1)
page.get_by_role("button", name="Menu", expanded=False)
page.get_by_role("button", name="Hidden item", include_hidden=True)
```
Other options: `disabled`, `pressed`, `selected`. Common roles: button, link, textbox, checkbox,
radio, combobox, listbox, option, heading, img, list, listitem, table, row, cell, dialog,
navigation, tab, menuitem.

Text matching:
```python
page.get_by_text("Login")  # substring, case-insensitive
page.get_by_text("Login", exact=True)  # exact, case-sensitive
page.get_by_text(re.compile("^log", re.I))  # regular expression
```

### 3. Generic `locator()`: CSS (XPath is banned here)
```python
page.locator("#username")  # id
page.locator(".inventory_item")  # class
page.locator("input[type='password']")  # tag + attribute
page.locator("a[href*='cart']")  # attribute contains
page.locator("[data-test^='add-to-cart']")  # starts with
page.locator("ul > li")  # direct child
```
Playwright-specific selectors: `button:has-text('Login')`, `button:text-is('Login')`,
`div:has(h1)`, `li:visible`, `input:not([disabled])`.

### 4. Narrowing and combining
| Method | Purpose | Example |
|---|---|---|
| `.first` / `.last` | first or last match | `page.locator(".item").first` |
| `.nth(n)` | zero-based index (prefer `filter`) | `page.locator(".item").nth(2)` |
| `.filter(has_text=)` | keep matches containing text | `items.filter(has_text="Backpack")` |
| `.filter(has_not_text=)` | drop matches containing text | `items.filter(has_not_text="Sold out")` |
| `.filter(has=)` | keep matches containing a child | `items.filter(has=page.get_by_role("button"))` |
| `.filter(has_not=)` | drop matches containing a child | `items.filter(has_not=page.locator(".badge"))` |
| `.locator()` chaining | search inside a parent | `page.locator(".item").locator("button")` |
| `.and_()` | must match both | `page.get_by_role("button").and_(page.get_by_title("Save"))` |
| `.or_()` | match either | `page.get_by_text("Error").or_(page.get_by_text("Failed"))` |

Click the button inside one specific product card:
```python
page.get_by_test_id("inventory-item").filter(has_text="Sauce Labs Backpack").get_by_role(
    "button", name="Add to cart"
).click()
```

### 5. Frames, shadow DOM, focus
```python
page.frame_locator("#payment-frame").get_by_label("Card number")  # iframe
page.locator("my-element").locator("button")  # CSS pierces open shadow roots
page.locator(":focus")  # focused element
```

### 6. Several matches
```python
items = page.get_by_test_id("inventory-item")
items.count()  # number of matches
items.all()  # list of locators
items.all_inner_texts()  # list of texts
```
