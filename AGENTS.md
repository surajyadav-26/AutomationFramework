# Automation framework

BDD test framework (pytest-bdd + Playwright + requests) for UI, API, visual and accessibility
checks of the application under test (none yet). No Docker anywhere. README.md is the map.

## Structure (an "area", e.g. cart, ties the folders together; the scaffold creates them)
- features/<suite>/<area>/   Gherkin, first line tagged @ui/@api/@visual/@accessibility (+ @smoke)
- steps/<suite>/<area>/      glue only, no selectors/URLs/HTTP; steps/<suite>/conftest.py = suite fixtures
- shared/                    fixtures and steps used by two or more areas or browser suites (never by api)
- pages/<area>/  pages/components/   page objects (all selectors) and reusable page parts
- clients/<area>/            API clients (all endpoints)
- core/                      settings, browser, api, visual, data, reporting (+ the two pytest plugins)
- test_data/ config/         usernames and schemas; URLs per environment
- baselines/<os>/<browser>/<WxH>/<area>/  visual baselines, local per machine and gitignored

## Rules (enforced by lint-imports and tools/check_rules.py)
- features -> steps -> shared -> pages/clients -> core. core never imports upwards.
- Areas never import each other; share via shared/, pages/components/ or core/.
- steps/api never imports pages, shared or Playwright; browser suites never import clients.
- No selectors, URLs or raw HTTP in steps. No duplicate step text per suite.
- Locators: get_by_role > get_by_label > get_by_text > get_by_test_id > CSS. No XPath, nth-child
  chains or sleeps; locators live in pages/ only. See the Locator sections of docs/CONTRIBUTING.md.
- Tags: registered in pyproject.toml and listed in docs/TAGS.md. Step wording: docs/VOCABULARY.md.
- Passwords only from APP_PASSWORD / API_PASSWORD env vars; never committed. prod needs ALLOW_PROD=true.
- Never skip, xfail or delete a failing test to pass a gate. Fix the root cause.
- Framework files are fingerprinted (framework.manifest.json): after changing core/, tools/, tests_framework/,
  suite conftests, pins or rule config run `python tools/fingerprint.py --update`. Hooks: `make hooks`.

## Commands
New area or component: `python tools/scaffold.py area <name> --suites ui,api` (never create folders by hand).
`make bootstrap | hooks | fingerprint | install | check | api | ui | smoke | visual | accessibility | cross-browser | area | scaffold | test-framework | mutation | audit | doctor | update-baselines | parallel | report | serve`

Code in core/ and tools/ is covered by tests_framework/ (coverage gate 95%); run `make test-framework`
after changing either. `make check` also runs mypy; add type hints to new code.
Never edit reports/ baselines/ *.lock by hand.
