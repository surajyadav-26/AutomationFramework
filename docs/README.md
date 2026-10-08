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

## Configuration reference
Set these in `.env` (copy `.env.example`), per environment in `.env.<TEST_ENV>`, or as real environment
variables. Precedence, highest first: real environment variables, `.env.<TEST_ENV>`, `.env`, then
`config/<TEST_ENV>.env`. A wrong value stops the run with a message naming the setting.

| Key | Default | Meaning |
|---|---|---|
| `TEST_ENV` | `qa` | which `config/<name>.env` to use |
| `APP_URL` / `API_URL` | from `config/<TEST_ENV>.env` | base URLs; must start with `http://` or `https://` |
| `APP_PASSWORD` / `API_PASSWORD` | none, required | passwords of the UI and API users; only from env or `.env*`, never committed |
| `LOG_RETENTION_DAYS` | `7` | daily log files older than this are deleted (`0` keeps all) |
| `TRACE_MODE` / `VIDEO_MODE` | `retain-on-failure` | Playwright trace and video: `off`, `on`, `retain-on-failure` |
| `ATTACH_TRACE_AND_VIDEO` | `true` | put trace and video in the Allure report. **A trace records typed passwords**, so CI sets this to `false`; traces then stay in the run's private `playwright-output` artifact |
| `ALLURE_AUTO_OPEN` / `ALLURE_THEME` | `true` / `dark` | open the report after a run (never in CI); `dark` or `light` |
| `A11Y_FAIL_IMPACT` | `serious` | lowest axe impact that fails an accessibility test |
| `API_TIMEOUT` / `API_MODE` | `15` / `live` | request timeout in seconds; `live` or offline `stub` |
| `RERUN_COUNT` / `RERUN_DELAY` | `1` / `1` | reruns after infrastructure errors only, and the pause in seconds |
| `VISUAL_IGNORE_ANTIALIASING` | `false` | ignore 1-2px wide visual differences |

### Secrets in reports
API requests and responses attached to Allure pass through `core/api/redaction.py`: passwords, tokens,
cookies, authorization headers and API keys are replaced by `***`. `tools/check_rules.py` also fails if a
secret literal is assigned in a committed file, or if the actual value of a secret setting from your
`.env` or environment appears in any committed file.

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

## Quality gates
| Gate | Command | What it checks |
|---|---|---|
| Lint and format | `ruff check .` / `ruff format --check .` | style and common bugs |
| Architecture | `lint-imports`, `python tools/check_rules.py` | layering, no selectors/URLs/HTTP in steps, locator rules |
| Static typing | `mypy` (config in `pyproject.toml`) | type errors in `core`, `pages`, `clients`, `tools`, `steps` |
| Framework self-tests | `make test-framework` | behaviour of `core/` and `tools/`, with a **95% coverage** floor |
| Dependency scan | `make audit` (`pip-audit`) | known vulnerabilities in the pinned packages |

`make check` runs the first three; the CI `lint` job runs all of them. Tool pins live in
`requirements-quality.lock` (kept apart from `requirements.lock` so test jobs install less). To work on
the framework itself: `make install-dev`. Using a virtualenv is recommended; a clean one built from the
two lock files passes every gate.

### Per-environment secrets
Precedence, highest first: real environment variables, `.env.<TEST_ENV>` (for example `.env.stage`),
`.env`, then the URLs in `config/<TEST_ENV>.env`. All `.env*` files except `.env.example` are gitignored.

## Framework self-tests
`tests_framework/` tests the framework itself (visual comparator, masking, baseline paths, settings
parsing, log retention, cleanup, schema validation, HTTP client, Allure helpers and
`tools/check_rules.py`). They are offline, take about a second and have their own pytest config, so
they never touch Allure results or logs of a normal run:
`python -m pytest -c tests_framework/pytest.ini tests_framework` (or `make test-framework`).
The CI `lint` job runs them. Run them after changing anything in `core/` or `tools/`.

## Reporting extras
- Every failing browser test attaches its **Playwright trace** (`trace.zip`) and **video** to the Allure
  result, kept according to `TRACE_MODE` / `VIDEO_MODE`. Download the zip and run
  `python -m playwright show-trace <trace.zip>`.
- Page objects log their actions (open, log in, expect ...) to `logs/application-YYYY-MM-DD.log`;
  passwords are never logged.
- CI `report` job: merges the Allure results of all jobs, keeps run history (trend graphs) in the
  Actions cache, uploads the report as the `allure-report` artifact and, on `main`, publishes it to
  GitHub Pages. Each run also gets a results table in its job summary (`tools/ci_summary.py`).

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

## Visual testing details
- **Viewports:** desktop 1280x720 and a phone 375x667 (`I am using a phone-sized screen`). Baselines
  are keyed by the page's actual viewport, so the two never share a file.
- **Volatile content:** page objects declare `hidden_selectors` (made invisible in place, layout and
  neighbours stay in the picture, e.g. the random prices) or `masked_selectors` (painted over with a
  solid box that follows the element size).
- **Anti-aliasing:** `VISUAL_IGNORE_ANTIALIASING=true` ignores differences only 1-2 pixels wide. Off by
  default because it would also hide a real 1px change such as a border colour.
- **Per test limit:** `assert_matches_baseline(name, page_object, max_ratio=...)` overrides the 0.1%.
- Failures save `<name>-<browser>-<WxH>-actual.png` / `-diff.png` in `reports/visual/`.
- In CI, the `cross-browser` job adds the visual suite for firefox and webkit once their linux
  baselines are committed.

## Reliability settings (`.env`)
| Key | Default | Meaning |
|---|---|---|
| `API_TIMEOUT` | `15` | seconds before an API request times out |
| `API_MODE` | `live` | `live` = the real dummyjson; `stub` = in-process fake of the auth endpoint, no network (proves the test logic, not the real service) |
| `RERUN_COUNT` | `1` | reruns after an infrastructure error; `0` disables. `--reruns N` on the command line wins |
| `RERUN_DELAY` | `1` | seconds between reruns |

Tests that were retried are listed in a "retried after infrastructure errors" section at the end of
the run, so flaky infrastructure stays visible.

## Retries
Reruns happen only for infrastructure errors (timeouts, connection errors, `net::ERR_*`); assertion
failures are never retried. The count is `RERUN_COUNT` (default 1). The patterns live in `pytest.ini`
and are checked by `tests_framework/test_rerun_filter.py`.

## Architecture
`features -> steps -> pages/clients -> core`; see AGENTS.md. Enforced by `lint-imports`
(.importlinter) and `tools/check_rules.py`.
