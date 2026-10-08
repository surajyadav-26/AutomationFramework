# Contributing

1. Write or extend a `.feature` file under `features/<suite>/<area>/`. The first line tags the
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
