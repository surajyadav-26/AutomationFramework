# Automation framework

BDD test automation for UI, API and visual checks. Python 3.12, pytest, pytest-bdd (Gherkin),
Playwright, requests, Allure. No Docker anywhere.

| Suite  | Target                                   | Feature                                        |
|--------|------------------------------------------|------------------------------------------------|
| UI     | https://www.saucedemo.com                | features/ui/login.feature                 |
| API    | https://dummyjson.com `POST /auth/login` | features/api/user.feature                 |
| Visual | https://www.saucedemo.com                | features/visual/login_visual.feature      |
| Accessibility | https://www.saucedemo.com         | features/accessibility/login_accessibility.feature |

## Setup
```
# uses your installed Python 3.12 directly (no virtualenv)
make install                                     # pip install -r requirements.lock + playwright chromium
cp .env.example .env                             # then set APP_PASSWORD and API_PASSWORD
```
URLs live in `config/<TEST_ENV>.env` (`TEST_ENV` defaults to `qa`). Passwords come only from
the `APP_PASSWORD` / `API_PASSWORD` environment variables (or your gitignored `.env`).
In CI they are read from the repository secrets of the same names.

## Run
`make api | ui | smoke | visual | accessibility | cross-browser | parallel | check`, `make report` / `make serve` (needs the
Allure CLI installed separately). Allure results are written to `reports/allure-results`
together with `environment.properties`; failure screenshots, API request/response and visual
Baseline/Actual/Diff images are attached.

## Logs, traces and video (configurable in `.env`)
| Key | Default | Meaning |
|---|---|---|
| `LOG_RETENTION_DAYS` | `7` | `logs/application-*.log` files not modified for more days are deleted at start (`0` keeps all) |
| `TRACE_MODE` | `retain-on-failure` | Playwright trace: `off`, `on` or `retain-on-failure` |
| `VIDEO_MODE` | `retain-on-failure` | Playwright video: `off`, `on` or `retain-on-failure` |
| `ALLURE_AUTO_OPEN` | `true` | build `reports/allure-report` and open it in the browser when a run ends (needs the Allure CLI on PATH; never when `CI` is set) |
| `A11Y_FAIL_IMPACT` | `serious` | lowest axe impact that fails an accessibility test: `minor`, `moderate`, `serious`, `critical` |
| `ALLURE_THEME` | `dark` | report theme `dark` or `light`; a theme the viewer picked in the browser wins |

One log file per day, `logs/application-YYYY-MM-DD.log`, is shared by ui, api and visual
(and by parallel workers; lines carry the process id). Traces and videos are written to
`reports/playwright/`; open a trace with `python -m playwright show-trace <trace.zip>`.
Passing `--tracing` / `--video` on the command line overrides `.env`.

## Accessibility
`@accessibility` scenarios scan the page with axe-core (axe-playwright-python) against WCAG 2.x
level A/AA rules. A test fails on violations at or above `A11Y_FAIL_IMPACT` (default `serious`);
every violation, whatever its impact, is attached to the Allure report as JSON. axe best-practice
rules (for example `page-has-heading-one`, `region`, both moderate on saucedemo) are not scanned.

## Cross-browser
Browser suites (ui, accessibility, visual) run on chromium by default. Pick browsers with the
pytest-playwright option, repeated per browser: `pytest steps --browser firefox --browser webkit`,
or `make cross-browser` for all three. The API suite is browser independent and runs once.
Visual baselines are per browser (`baselines/<os>/<browser>/...`), so firefox and webkit
baselines must be generated before their visual tests pass (`make update-baselines` locally, or the
*update-baselines* workflow for linux, which now covers all three browsers). In Allure a
cross-browser run shows one group per browser, e.g. `UI / Auth (firefox)`.
CI: the `cross-browser` job runs ui and accessibility on firefox and webkit; the regular `visual`
job stays on chromium.

## Framework self-tests
`tests_framework/` tests the framework itself (visual comparator, masking, baseline paths, settings
parsing, log retention, cleanup, schema validation, HTTP client, Allure helpers and
`tools/check_rules.py`). They are offline, take about a second and have their own pytest config, so
they never touch Allure results or logs of a normal run:
`python -m pytest -c tests_framework/pytest.ini tests_framework` (or `make test-framework`).
The CI `lint` job runs them. Run them after changing anything in `core/` or `tools/`.

## Allure suites
The Suites tab groups tests by suite type. A full run shows `UI`, `API` and `Visual` at the top
level. A `-m smoke` run shows one `Smoke` group with `UI`, `API` and `Visual` underneath.
The next level is the area (the `steps/<suite>/` folder, e.g. `Auth`).

## Visual baselines (no Docker, so rendering differs per OS)
Baselines are stored per `baselines/<os>/<browser>/<WxH>/<name>.png`.
- Only the **linux** baselines are committed; they come from the CI runner and are the source of truth.
- `windows` and `macos` baselines are gitignored, local conveniences: create them with
  `make update-baselines` on that machine.
- A missing baseline **fails** the test. To refresh the linux baselines run the
  *update-baselines* workflow (Actions → Run workflow); it opens a pull request to review.
- Comparison: Pillow pixel diff, per-pixel tolerance 10, max 0.1% of pixels differing,
  viewport 1280x720, UTC, en-US, animations disabled. Volatile areas are masked per page object
  (`volatile_selectors`).

CI first-time setup (remote, secrets, linux baselines): see [CI_SETUP.md](CI_SETUP.md).

## Retries
At most one rerun, only for infrastructure errors (Playwright timeouts, connection errors,
`net::ERR_*`). Assertion failures are never retried.

## Architecture
`features -> steps -> pages/clients -> core`; see AGENTS.md. Enforced by `lint-imports`
(.importlinter) and `tools/check_rules.py`.
