PYTHON ?= python
PYTEST ?= $(PYTHON) -m pytest -q --tb=short

.PHONY: install check api ui smoke visual update-baselines parallel report serve

install:
	$(PYTHON) -m pip install -r requirements.lock
	$(PYTHON) -m playwright install --with-deps chromium

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

update-baselines:
	$(PYTEST) steps/visual --update-baselines

parallel:
	$(PYTEST) steps -n 2

report:
	allure generate reports/allure-results -o reports/allure-report --clean

serve:
	allure serve reports/allure-results
