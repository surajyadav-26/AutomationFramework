PYTHON ?= python
PYTEST ?= $(PYTHON) -m pytest -q --tb=short

.PHONY: install check api ui smoke visual accessibility cross-browser update-baselines parallel report serve

install:
	$(PYTHON) -m pip install -r requirements.lock
	$(PYTHON) -m playwright install --with-deps chromium firefox webkit

check:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	lint-imports
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

update-baselines:
	$(PYTEST) steps/visual --update-baselines

parallel:
	$(PYTEST) steps -n 2

report:
	allure generate reports/allure-results -o reports/allure-report --clean

serve:
	allure serve reports/allure-results
