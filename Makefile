PYTHON ?= python
PYTEST ?= $(PYTHON) -m pytest -q --tb=short

.PHONY: bootstrap hooks fingerprint area scaffold install check api ui smoke visual accessibility cross-browser test-framework mutation audit doctor update-baselines parallel report serve

install:
	$(PYTHON) -m pip install -r requirements.lock
	$(PYTHON) -m playwright install --with-deps chromium firefox webkit

check:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	lint-imports
	$(PYTHON) -m mypy
	$(PYTHON) tools/check_rules.py

api:
	$(PYTEST) steps/api

ui:
	$(PYTEST) steps/ui

smoke:
	$(PYTEST) steps -m smoke

visual:
	$(PYTEST) steps/visual

accessibility:
	$(PYTEST) steps/accessibility

# all browser-based suites on chromium, firefox and webkit (visual needs per-browser baselines)
cross-browser:
	$(PYTEST) steps/ui steps/accessibility steps/visual --browser chromium --browser firefox --browser webkit

# self-tests for core/ and tools/ (offline, about a second, separate pytest config)
test-framework:
	$(PYTHON) -m pytest -c tests_framework/pytest.ini tests_framework -q --tb=short --cov --cov-fail-under=95 --cov-report=term-missing:skip-covered

# break the framework code on purpose and check the self-tests notice (about 10 minutes)
mutation:
	$(PYTHON) tools/mutation_check.py

# does this Python match requirements.lock and .python-version?
doctor:
	$(PYTHON) tools/check_env.py

# dependency vulnerability scan (needs network)
audit:
	$(PYTHON) -m pip_audit -r requirements.lock --no-deps --disable-pip

update-baselines:
	$(PYTEST) steps/visual --update-baselines

parallel:
	$(PYTEST) steps -n 2

report:
	allure generate reports/allure-results -o reports/allure-report --clean

serve:
	allure serve reports/allure-results

# one feature area across all suites: make area NAME=auth
area:
	$(PYTEST) steps --area $(NAME)

# create a new area or component: make scaffold ARGS="area cart --suites ui,api"
scaffold:
	$(PYTHON) tools/scaffold.py $(ARGS)

# set up this machine and verify it (installs, .env, git hooks); make bootstrap ARGS="--check" only verifies
bootstrap:
	$(PYTHON) tools/bootstrap.py $(ARGS)

# git hooks that run the framework rules before every commit and push
hooks:
	$(PYTHON) tools/hooks.py install

# is this copy the same framework? after an intended framework change: make fingerprint ARGS=--update
fingerprint:
	$(PYTHON) tools/fingerprint.py $(ARGS)
