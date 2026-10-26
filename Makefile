SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help venv up down reset psql sample test raw-table load inspect

# Load local settings (POSTGRES_*) from .env when it exists, and pass them to every command.
-include .env
export

# dbt v2 loads the Postgres adapter only with this flag (see docs/0001-dbt-v2-experimental-postgres.md).
export DBT_ALLOW_EXPERIMENTAL_ADAPTERS := true

PYTHON ?= python3.12
VENV := .venv

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

venv: ## Create .venv and install the pinned requirements
	@command -v $(PYTHON) >/dev/null || { echo "error: $(PYTHON) not found. Install Python 3.12."; exit 1; }
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements-dev.txt

up: ## Start the database and wait until it is healthy
	docker compose up -d --wait

down: ## Stop the database (data is kept)
	docker compose down

reset: ## Delete all database data and start clean
	docker compose down -v
	docker compose up -d --wait

psql: ## Open psql inside the database container
	docker compose exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

sample: ## Generate synthetic sample data (RECORDS=2000 SEED=42)
	$(VENV)/bin/python sample_data/generate.py --records $(or $(RECORDS),2000) --seed $(or $(SEED),42)

test: ## Run the test suite
	$(VENV)/bin/pytest

raw-table: ## Apply the table definition in sql/raw_spotify_streams.sql
	docker compose exec -T db psql -v ON_ERROR_STOP=1 -U $(POSTGRES_USER) -d $(POSTGRES_DB) < sql/raw_spotify_streams.sql

load: ## Load streaming history into raw.spotify_streams (SOURCE=sample_data)
	$(VENV)/bin/python ingest/load.py --source $(or $(SOURCE),sample_data)

inspect: ## Show the structure of an export folder (SOURCE=data)
	@test -n "$(SOURCE)" || { echo "error: SOURCE is required, for example make inspect SOURCE=data"; exit 2; }
	$(VENV)/bin/python ingest/inspect_export.py $(SOURCE)
