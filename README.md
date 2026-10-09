# Automation framework

BDD test automation for UI, API, visual and accessibility checks. Python 3.12, pytest, pytest-bdd
(Gherkin), Playwright, requests, Allure. No Docker anywhere.

| Suite | Target | Feature |
|---|---|---|
| UI | https://www.saucedemo.com | features/ui/login.feature |
| API | https://dummyjson.com `POST /auth/login` | features/api/user.feature |
| Visual | https://www.saucedemo.com | features/visual/login_visual.feature |
| Accessibility | https://www.saucedemo.com | features/accessibility/login_accessibility.feature |

Layering: `features -> steps -> pages/clients -> core` (see AGENTS.md), enforced by `lint-imports`
(configured in `pyproject.toml`) and `tools/check_rules.py`.

## Setup
```
python -m pip install -r requirements.lock          # make install also installs the browsers
python -m playwright install --with-deps chromium firefox webkit
cp .env.example .env                                # then set APP_PASSWORD and API_PASSWORD
python tools/check_env.py                           # make doctor: does this Python match the locks?
```
A virtualenv is not required. `requirements.in` lists the direct dependencies, `requirements.lock` pins them
and everything they pull in (test runner, browser tools and the quality tools such as mypy), and
`.python-version` is `3.12`. To change dependencies: edit `requirements.in`, build a clean virtualenv from
it, run `pip freeze` into `requirements.lock`, then `make doctor`. Add libraries only after agreeing it
with the team.

## Run
`make` is optional. Every target is a shortcut for a plain command:

| make | plain command |
|---|---|
| `make ui` / `api` / `visual` / `accessibility` | `python -m pytest steps/ui` (or `steps/api`, `steps/visual`, `steps/accessibility`) |
| `make smoke` | `python -m pytest steps -m smoke` |
| `make parallel` | `python -m pytest steps -n 2` |
| `make cross-browser` | `python -m pytest steps --browser chromium --browser firefox --browser webkit` |
| `make update-baselines` | `python -m pytest steps/visual --update-baselines` |
| `make check` | `ruff check .`, `ruff format --check .`, `lint-imports`, `mypy`, `python tools/check_rules.py` |
| `make test-framework` | `python -m pytest -c tests_framework/pytest.ini tests_framework --cov --cov-fail-under=95` |
| `make mutation` / `doctor` / `audit` | `python tools/mutation_check.py` / `python tools/check_env.py` / `pip-audit -r requirements.lock --no-deps --disable-pip` |
| `make report` / `serve` | `allure generate ...` / `allure serve ...` (needs the Allure CLI) |

## Configuration reference
Set these in `.env` (copy `.env.example`), per environment in `.env.<TEST_ENV>`, or as real environment
variables. Precedence, highest first: real environment variables, `.env.<TEST_ENV>`, `.env`, then
`config/<TEST_ENV>.env` (the URLs). All `.env*` files except `.env.example` are gitignored. A wrong value
stops the run with a message naming the setting.

| Key | Default | Meaning |
|---|---|---|
| `TEST_ENV` | `qa` | which `config/<name>.env` to use |
| `APP_URL` / `API_URL` | from `config/<TEST_ENV>.env` | base URLs; must start with `http://` or `https://` |
| `APP_PASSWORD` / `API_PASSWORD` | none, required | passwords of the UI and API users; only from env or `.env*`, never committed |
| `LOG_RETENTION_DAYS` | `7` | `logs/application-*.log` files not modified for more days are deleted at start (`0` keeps all) |
| `TRACE_MODE` / `VIDEO_MODE` | `retain-on-failure` | Playwright trace and video: `off`, `on`, `retain-on-failure` (`--tracing` / `--video` on the command line win) |
| `ATTACH_TRACE_AND_VIDEO` | `true` | put trace and video in the Allure report. **A trace records typed passwords**, so CI sets this to `false`; traces then stay in the run's private `playwright-output` artifact |
| `ALLURE_AUTO_OPEN` / `ALLURE_THEME` | `true` / `dark` | build and open the Allure report when a run ends (never in CI; needs the Allure CLI); `dark` or `light` (a theme picked in the browser wins) |
| `A11Y_FAIL_IMPACT` | `serious` | lowest axe impact that fails an accessibility test: `minor`, `moderate`, `serious`, `critical` |
| `A11Y_INCLUDE_BEST_PRACTICES` | `true` | also scan axe best-practice rules; they are reported and only fail a test if the impact threshold is set low |
| `API_TIMEOUT` / `API_MODE` | `15` / `live` | request timeout in seconds; `live` = the real dummyjson, `stub` = in-process fake of the auth endpoint with no network (proves the test logic, not the real service) |
| `RERUN_COUNT` / `RERUN_DELAY` | `1` / `1` | reruns after infrastructure errors only, and the pause in seconds (`--reruns N` on the command line wins) |
| `VISUAL_IGNORE_ANTIALIASING` | `false` | ignore 1-2px wide visual differences |

### Secrets in reports
API requests and responses attached to Allure pass through `core/api/redaction.py`: passwords, tokens,
cookies, authorization headers and API keys are replaced by `***`. `tools/check_rules.py` also fails if a
secret literal is assigned in a committed file, or if the actual value of a secret setting from your `.env`
or environment appears in any committed file.

## Suites

### Visual (no Docker, so rendering differs per OS)
- **Baselines are local.** They are stored per `baselines/<os>/<browser>/<WxH>/<name>.png` and are
  **gitignored**: every developer creates their own with `make update-baselines` and checks the images by
  eye. A missing baseline **fails** the test. `tools/check_rules.py` checks the folder layout, flags orphan
  images that no step uses, and fails if a windows or macos baseline is committed.
- **Comparison:** Pillow pixel diff, per-pixel tolerance 10, at most 0.1% of pixels differing, viewport
  1280x720 (and a phone 375x667 via `I am using a phone-sized screen`), UTC, en-US, animations disabled.
  Screenshots wait for the load event, web fonts and all images (not for "network idle").
- **Volatile content:** page objects declare `hidden_selectors` (made invisible in place; layout and
  neighbours stay in the picture, e.g. the random prices) or `masked_selectors` (painted over with a solid
  box that follows the element size).
- **Anti-aliasing:** `VISUAL_IGNORE_ANTIALIASING=true` ignores differences only 1-2 pixels wide. Off by
  default because it would also hide a real 1px change such as a border colour.
- **Threshold in practice:** 0.1% of a 1280x720 screenshot is about 920 pixels, so a few changed words can
  pass. Tighten it per test with `assert_matches_baseline(name, page_object, max_ratio=...)`.
- Failures attach Baseline, Actual and Diff to Allure and save `<name>-<browser>-<WxH>-actual.png` /
  `-diff.png` in `reports/visual/`.

### Accessibility
`@accessibility` scenarios scan the page with axe-core (axe-playwright-python) against WCAG 2.x level A/AA
rules, plus axe's best-practice rules (for example `page-has-heading-one`, `region`; both moderate on
saucedemo). A test fails on violations at or above `A11Y_FAIL_IMPACT`; every violation, whatever its impact,
is attached to the Allure report as JSON.

### Cross-browser
Browser suites (ui, accessibility, visual) run on chromium by default. Pick browsers with the
pytest-playwright option, repeated per browser: `pytest steps --browser firefox --browser webkit`, or
`make cross-browser` for all three. The API suite has no browser and runs once. Visual baselines are per
browser, so generate them for each browser first. In Allure a cross-browser run shows one group per browser,
e.g. `UI / Login (firefox)`.

### API
`API_MODE=stub` runs the API suite against an in-process fake of the auth endpoint, so it works offline
and when dummyjson is down. Retries happen only for infrastructure errors (timeouts, connection errors,
`net::ERR_*`), never for assertion failures; the patterns live in `pyproject.toml` and are checked by
`tests_framework/test_rerun_filter.py`. Tests that were retried are listed at the end of the run under
"retried after infrastructure errors", so flaky infrastructure stays visible.

## Reports and logs
- **Allure results** go to `reports/allure-results` with `environment.properties`. Failures attach a
  screenshot, the Playwright **trace** (`trace.zip`; open with `python -m playwright show-trace <file>`)
  and **video**, and API calls attach their redacted request and response.
- **Suites tab:** a full run groups tests as `UI`, `API`, `Visual` and `Accessibility`; a `-m smoke` run shows
  one `Smoke` group with those underneath. The next level is named after the step file (`test_login_steps.py`
  gives `Login`).
- **Logs:** one file per day, `logs/application-YYYY-MM-DD.log`, shared by every suite and by parallel
  workers (lines carry the process id). Page objects log their actions; passwords are never logged.

## Quality gates
| Gate | Command | What it checks |
|---|---|---|
| Lint and format | `ruff check .` / `ruff format --check .` | style and common bugs |
| Architecture | `lint-imports`, `python tools/check_rules.py` | layering, no selectors/URLs/HTTP in steps, locator rules, baseline layout, leaked secrets |
| Static typing | `mypy` (config in `pyproject.toml`) | type errors in `core`, `pages`, `clients`, `tools`, `steps` |
| Framework self-tests | `make test-framework` | behaviour of `core/` and `tools/`, with a **95% coverage** floor |
| Test the tests | `make mutation` | deliberately breaks the code in 27 places and fails if the self-tests do not notice; weekly in CI, about 10 minutes |
| Environment | `make doctor` | installed packages equal `requirements.lock`, Python matches `.python-version`, every direct dependency is pinned; warns about the old `allure-pytest` that clashes with `allure-pytest-bdd` |
| Dependency scan | `make audit` (`pip-audit`) | known vulnerabilities in the pinned packages |

`tests_framework/` holds the framework's own tests (comparator, settings, redaction, rules checker, the
browser layer against local HTML with a real Chromium, and more). It has its own pytest config, so it never
touches the Allure results or logs of a normal run. Run it after changing anything in `core/` or `tools/`.

## CI (GitHub Actions)
`ci.yml` stages: `lint` (all quality gates) -> `api` -> `ui-smoke` -> `ui-full` -> `accessibility` and
`cross-browser` (firefox, webkit) -> `report`. Every job checks out the repo and runs the shared
`.github/actions/setup` action (Python from `.python-version`, `pip install -r requirements.lock`, only the
browsers the job needs, and an early check that the repository secrets exist). Jobs have read-only
permissions and a 30 minute timeout, and a newer push to a pull request cancels the older run.
`mutation.yml` runs the mutation check weekly. The `report` job merges the Allure results of all jobs, keeps
run history (trend graphs) in the Actions cache, uploads the report as the `allure-report` artifact and,
on `main`, publishes it to GitHub Pages; each run also gets a results table in its job summary.

**Visual tests do not run in CI**: their baselines are local to a machine (above). To bring them to CI
later, generate baselines on a linux runner, commit them under `baselines/linux/`, and add a `visual` job.

### First-time setup
1. `git remote add origin <url>` and `git push -u origin main`.
2. Settings > Secrets and variables > Actions: add `APP_PASSWORD` and `API_PASSWORD`.
3. Optional, to publish the report: Settings > Pages > Source: **GitHub Actions**. Without it the publish
   steps are skipped without failing the run.
4. Push or open a pull request. If `api` fails with "Repository secret ... is not set", step 2 is missing;
   a dummyjson read timeout is the public service being slow, so re-run the job.

## Architecture
`features -> steps -> pages/clients -> core`. See AGENTS.md for the rules and CONTRIBUTING.md for how to add
a scenario, a page object or an API client.
