# Tags

Tags go on the first line of a `.feature` file (feature level) or above a scenario. pytest-bdd turns every
tag into a pytest marker, so each tag must be registered in `pyproject.toml` (`--strict-markers` is on).
`tools/check_rules.py` fails when a feature uses a tag that is not registered, or when a registered tag is
missing from this file.

## Suite tags (exactly one per feature file, matching its folder)

| Tag | Meaning | Run with |
|---|---|---|
| `@ui` | browser UI behaviour | `pytest steps/ui` or `-m ui` |
| `@api` | HTTP API behaviour | `pytest steps/api` or `-m api` |
| `@visual` | screenshot comparison against a local baseline | `pytest steps/visual` or `-m visual` |
| `@accessibility` | axe-core WCAG scan | `pytest steps/accessibility` or `-m accessibility` |

A feature in `features/ui/` must be tagged `@ui`, and so on; the checker enforces it.

## Selection tags

| Tag | Meaning | Run with |
|---|---|---|
| `@smoke` | the quick checks that prove the system is alive; one per suite is enough | `pytest steps -m smoke` |

## Area markers (added automatically, never typed)

Every test gets a marker named after its area, the folder under the suite: a test in
`steps/ui/auth/` is marked `auth`. Run one area across all suites with `pytest --area auth`
(repeatable) or `pytest -m auth`. Areas are discovered from `features/<suite>/<area>/`; the names `ui`,
`api`, `visual`, `accessibility`, `smoke`, `shared` and `components` are reserved.

## Adding a tag

1. Add it to `markers` in `pyproject.toml`.
2. Describe it in this file (the name with its `@`).
3. Use it in a feature. `make check` fails if one of these steps is missing.
