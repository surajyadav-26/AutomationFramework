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
7. Before pushing: `make check` and the suite you touched. Optional: `pre-commit install`.
8. Visual changes: do not commit windows/macos baselines. Run the *update-baselines*
   workflow and review the images in the resulting pull request.
9. Do not hand-edit `reports/`, `baselines/` or `requirements.lock` (regenerate the lock with
   `pip freeze` after an intentional dependency change).

## Locator guidelines
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
