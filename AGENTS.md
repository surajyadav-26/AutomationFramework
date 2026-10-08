# Automation framework

BDD test framework (pytest-bdd + Playwright + requests) for UI, API and visual
checks against saucedemo.com and dummyjson.com. No Docker anywhere.

## Structure
- features/{ui,api,visual,accessibility}/  Gherkin, tagged by suite (+ @smoke)
- steps/                     step definitions and fixtures, no selectors/URLs/HTTP
- pages/                     page objects (all selectors live here)
- clients/                   API clients (all endpoints live here)
- core/                      settings, browser, api, visual, data, reporting
- test_data/ config/         usernames and schemas; URLs per environment
- baselines/<os>/<browser>/<WxH>/  visual baselines; only linux is committed

## Architecture rules (enforced by lint-imports and tools/check_rules.py)
- features -> steps -> pages/clients -> core. core never imports upwards.
- steps/api never imports pages or Playwright; browser suites (ui, visual, accessibility) never import clients.
- No selectors, URLs or raw HTTP in steps. No duplicate step text per suite.
- Locators: get_by_role > get_by_label > get_by_text > get_by_test_id > CSS. No XPath, nth-child
  chains or sleeps; locators live in pages/ only. Read docs/LOCATORS.md before writing page objects.
- Passwords only from APP_PASSWORD / API_PASSWORD env vars; never committed.
- Never skip, xfail or delete a failing test to pass a gate. Fix the root cause.

## Commands
`make install | check | api | ui | smoke | visual | accessibility | cross-browser | test-framework | audit | doctor | update-baselines | parallel | report | serve`

Framework code (core/, tools/) is covered by tests_framework/ (coverage gate 95%); run `make test-framework`
after changing either. `make check` also runs mypy; add type hints to new code.
Never edit reports/ baselines/ *.lock by hand.
