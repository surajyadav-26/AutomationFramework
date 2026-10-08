# Contributing

1. Write or extend a `.feature` file under `features/<suite>/`. The first line tags the
   suite (`@ui`, `@api` or `@visual`); add `@smoke` to quick checks.
2. Reuse existing step wording from [VOCABULARY.md](VOCABULARY.md). Add new wording there too.
   Step text must be unique within a suite.
3. Put selectors in `pages/`, endpoints in `clients/`, shared plumbing in `core/`.
   Step files hold only Gherkin glue: no selectors, URLs or raw HTTP calls.
4. Respect the layering `steps -> pages/clients -> core`; `steps/api` never touches pages or
   Playwright, `steps/ui` and `steps/visual` never touch clients.
5. No hardcoded passwords. Use `settings.app_password` / `settings.api_password` and
   `core.data.factories.random_password()` for deliberately wrong ones.
6. Never skip, xfail or delete a failing test to pass a gate; fix the root cause.
7. Before pushing: `make check` (ruff, import rules, mypy, rules checker), `make test-framework` if you
   touched `core/` or `tools/`, and the suite you touched. New code gets type hints. Optional: `pre-commit install`.
8. Visual changes: do not commit windows/macos baselines. Run the *update-baselines*
   workflow and review the images in the resulting pull request.
9. Do not hand-edit `reports/`, `baselines/` or `requirements.lock` (regenerate the lock with
   `pip freeze` after an intentional dependency change).

## Locator guidelines
Full cheat sheet: [LOCATORS.md](LOCATORS.md).
- Prefer `get_by_role`, then `get_by_label`, then `get_by_text`: they describe what a user sees
  and double as a basic accessibility check.
- Use `get_by_test_id` (our `by_test()`, attribute `data-test`) when the page has no stable
  user-facing handle.
- Use CSS only for structure that nothing user-facing describes (for example the masked `.pricebar`).
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
    customer = customer_client.create(name=unique("cust"))      # unique values: no clashes in parallel
    cleanup.register(lambda: customer_client.delete(customer["id"]), "delete customer")
    return customer
```
The `cleanup` fixture (steps/conftest.py) runs the callbacks after the test, newest first, whether the
test passed or failed, and reports any callback that raised. tests_framework/test_steps_conftest.py
proves this with real pytest sessions. Pass data between steps with `target_fixture=`, not shared dicts.
Steps that two suites need go in `steps/_login_steps.py`-style shared modules (star-imported, because
pytest-bdd registers a step in the module that defines it); browser fixtures are in
`steps/_browser_fixtures.py`.
