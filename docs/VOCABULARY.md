# Step vocabulary

One list of the step wording each suite uses, so the same action is always phrased the same way. Add a
section per suite as steps are written. Parameters are in `{braces}`. A step text may appear once per
suite, and a step defined in `shared/` cannot be redefined by a browser suite (`make check` enforces both).

## How to list steps
```
## UI (steps/ui/<area>/test_<name>_steps.py)
- Given I am on the login page
- When I log in as the "{role}" user
- Then I see the dashboard
```
Mark a step defined once in `shared/` with "(shared)". Roles such as `{role}` come from
`test_data/users.json` (a JSON object of role to username; `test_data/users.<env>.json` overrides roles per
environment).

## Scaffolded areas
`tools/scaffold.py` gives every suite of a new area one wiring step, "the <area> page object is available"
(browser suites) or "the <area> client is available" (api). It only proves the files are connected: replace
it with the area's real steps and list them here.

## UI
_No steps yet._

## API
_No steps yet._

## Visual
_No steps yet._

## Accessibility
_No steps yet._
