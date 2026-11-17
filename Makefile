PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
IMAGE ?= pncp-pipeline:local

.PHONY: help setup lint format test test-live build run-local dbt-build dbt-test dbt-docs dashboard pre-commit-install clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "%-20s %s\n", $$1, $$2}'

setup: ## Create the virtualenv and install the project with dev dependencies
	@if [ ! -x "$(BIN)/python" ]; then \
		$(PYTHON) -m venv $(VENV) >/dev/null 2>&1 || ( \
			echo "ensurepip unavailable; bootstrapping pip with get-pip.py"; \
			rm -rf $(VENV); \
			$(PYTHON) -m venv --without-pip $(VENV); \
			curl -fsSL https://bootstrap.pypa.io/get-pip.py -o $(VENV)/get-pip.py; \
			$(BIN)/python $(VENV)/get-pip.py; \
			rm -f $(VENV)/get-pip.py; \
		); \
	fi
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"

lint: ## Run static checks
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .
	$(BIN)/mypy src

format: ## Auto-fix and format code
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

test: ## Run the test suite
	$(BIN)/pytest

test-live: ## Run the opt-in live PNCP integration test
	RUN_INTEGRATION=1 $(BIN)/pytest -m integration -s

build: ## Build the container image
	docker build -t $(IMAGE) .

run-local: ## Print the resolved configuration
	$(BIN)/python -m pncp_pipeline config

dbt-build: ## Build and test the dbt project against BigQuery
	$(BIN)/dbt build --project-dir dbt --profiles-dir dbt

dbt-test: ## Run dbt tests
	$(BIN)/dbt test --project-dir dbt --profiles-dir dbt

dbt-docs: ## Generate the dbt documentation site
	$(BIN)/dbt docs generate --project-dir dbt --profiles-dir dbt

dashboard: ## Export Gold marts for the static dashboard
	$(BIN)/python scripts/export_dashboard.py

pre-commit-install: ## Install the git hooks (optional)
	$(BIN)/pre-commit install

clean: ## Remove local build artefacts
	rm -rf $(VENV) .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage dist build
