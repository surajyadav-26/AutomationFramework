# Playwright locators cheat sheet (Python)

Reference for writing page objects. Rules of thumb first, details below.
All locators live in `pages/`, never in step files. `tools/check_rules.py` blocks XPath,
positional selectors, 3+ level child chains and manual sleeps.

## Rules of thumb
- Prefer `get_by_role`, then `get_by_label`, then `get_by_text`.
- Use `get_by_test_id` when the page has no stable user-facing handle. In this project the test id
  attribute is `data-test` (set in the root `conftest.py`), and `BasePage.by_test()` wraps it.
- Use CSS only for structure that nothing user-facing describes.
- Avoid long XPath chains and absolute paths such as `div > div > div:nth-child(3)`.
- Locators are lazy and auto-wait: no manual sleeps. Save a locator and reuse it.

## 1. Quick pick guide
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

## 2. Built-in locators (best to worst)
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
page.get_by_text("Login")                   # substring, case-insensitive
page.get_by_text("Login", exact=True)       # exact, case-sensitive
page.get_by_text(re.compile("^log", re.I))  # regular expression
```

## 3. Generic `locator()`: CSS (XPath is banned here)
```python
page.locator("#username")                    # id
page.locator(".inventory_item")              # class
page.locator("input[type='password']")       # tag + attribute
page.locator("a[href*='cart']")              # attribute contains
page.locator("[data-test^='add-to-cart']")   # starts with
page.locator("ul > li")                      # direct child
```
Playwright-specific selectors: `button:has-text('Login')`, `button:text-is('Login')`,
`div:has(h1)`, `li:visible`, `input:not([disabled])`.

## 4. Narrowing and combining
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
page.get_by_test_id("inventory-item") \
    .filter(has_text="Sauce Labs Backpack") \
    .get_by_role("button", name="Add to cart") \
    .click()
```

## 5. Frames, shadow DOM, focus
```python
page.frame_locator("#payment-frame").get_by_label("Card number")  # iframe
page.locator("my-element").locator("button")  # CSS pierces open shadow roots
page.locator(":focus")                        # focused element
```

## 6. Several matches
```python
items = page.get_by_test_id("inventory-item")
items.count()             # number of matches
items.all()               # list of locators
items.all_inner_texts()   # list of texts
```
