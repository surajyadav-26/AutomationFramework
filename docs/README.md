# Automation framework

BDD test automation for UI, API and visual checks. Python 3.12, pytest, pytest-bdd (Gherkin),
Playwright, requests, Allure. No Docker anywhere.

| Suite  | Target                                   | Feature                                        |
|--------|------------------------------------------|------------------------------------------------|
| UI     | https://www.saucedemo.com                | features/ui/auth/login.feature                 |
| API    | https://dummyjson.com `POST /auth/login` | features/api/auth/user.feature                 |
| Visual | https://www.saucedemo.com                | features/visual/auth/login_visual.feature      |

## Setup
```
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
make install                                     # pip install -r requirements.lock + playwright chromium
cp .env.example .env                             # then set APP_PASSWORD and API_PASSWORD
```
URLs live in `config/<TEST_ENV>.env` (`TEST_ENV` defaults to `qa`). Passwords come only from
the `APP_PASSWORD` / `API_PASSWORD` environment variables (or your gitignored `.env`).
In CI they are read from the repository secrets of the same names.

## Run
`make api | ui | smoke | visual | parallel | check`, `make report` / `make serve` (needs the
Allure CLI installed separately). Allure results are written to `reports/allure-results`
together with `environment.properties`; failure screenshots, API request/response and visual
Baseline/Actual/Diff images are attached.

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

## Retries
At most one rerun, only for infrastructure errors (Playwright timeouts, connection errors,
`net::ERR_*`). Assertion failures are never retried.

## Architecture
`features -> steps -> pages/clients -> core`; see AGENTS.md. Enforced by `lint-imports`
(.importlinter) and `tools/check_rules.py`.
