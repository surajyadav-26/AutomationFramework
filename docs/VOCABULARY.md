# Step vocabulary

Wording per suite. The two steps marked (shared) are defined once in `shared/login_steps.py` and used by
the visual and accessibility suites. Parameters are in `{braces}`. A step text may appear once per suite.

## UI (steps/ui/auth/test_login_steps.py)
- Given I am on the login page
- When I log in as the "{role}" user with a {valid|invalid} password
- Then I see the products page
- Then I see the login error "{message}"

## API (steps/api/auth/test_user_steps.py)
- When I request a token with valid credentials
- When I request a token with a wrong password
- Then the response status is {status}
- Then the response body matches the user schema
- Then the response contains an access token
- Then the response message is "{message}"

## Visual (steps/visual/auth/test_login_visual_steps.py)
- Given I am using a phone-sized screen (375x667; baselines are stored per viewport)
- Given I am viewing the login page (shared)
- When I sign in as the "{role}" user (shared)
- Then the login page matches the baseline
- Then the inventory page matches the baseline

## Accessibility (steps/accessibility/auth/test_login_accessibility_steps.py)
- Given I am viewing the login page
- When I sign in as the "{role}" user
- Then the login page has no blocking accessibility violations
- Then the inventory page has no blocking accessibility violations

Roles come from `test_data/users.json`: standard, locked_out, visual, no_username, api.

## New areas
`tools/scaffold.py` gives every suite of a new area one wiring step, "the <area> page object is available"
(browser suites) or "the <area> client is available" (api). It only proves the files are connected: replace it
with the area's real steps and list them here.
