PYTHON ?= python
PYTEST ?= $(PYTHON) -m pytest -q --tb=short

.PHONY: install check api ui smoke visual accessibility cross-browser test-framework audit doctor install-dev update-baselines parallel report serve

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

# does this Python match requirements*.lock and .python-version?
doctor:
	$(PYTHON) tools/check_env.py

# dependency vulnerability scan (needs network)
audit:
	$(PYTHON) -m pip_audit -r requirements.lock -r requirements-quality.lock --no-deps --disable-pip

# runtime plus quality tools (mypy, pip-audit, coverage), for working on the framework itself
install-dev:
	$(PYTHON) -m pip install -r requirements.lock -r requirements-quality.lock
	$(PYTHON) -m playwright install --with-deps chromium firefox webkit

update-baselines:
	$(PYTEST) steps/visual --update-baselines

parallel:
	$(PYTEST) steps -n 2

report:
	allure generate reports/allure-results -o reports/allure-report --clean

serve:
	allure serve reports/allure-results
