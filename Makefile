SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help up down reset psql psql-agent sample test raw-table roles lint-contract load inspect

# Load local settings (POSTGRES_*) from .env when it exists, and pass them to every command.
-include .env
export

# dbt v2 loads the Postgres adapter only with this flag (see docs/0001-dbt-v2-experimental-postgres.md).
export DBT_ALLOW_EXPERIMENTAL_ADAPTERS := true

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

up: ## Start the database and wait until it is healthy
	docker compose up -d --wait

down: ## Stop the database (data is kept)
	docker compose down

reset: ## Delete all database data and start clean
	docker compose down -v
	docker compose up -d --wait

psql: ## Open psql inside the database container
	docker compose exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)

psql-agent: ## Open psql as the agent role (read-only, curated data only)
	@test -n "$(AGENT_PASSWORD)" || { echo "error: AGENT_PASSWORD is required, see .env.example"; exit 2; }
	@docker compose exec -e PGPASSWORD=$(AGENT_PASSWORD) db psql -h localhost -U agent -d $(POSTGRES_DB)

sample: ## Generate synthetic sample data (RECORDS=2000 SEED=42)
	uv run python sample_data/generate.py --records $(or $(RECORDS),2000) --seed $(or $(SEED),42)

test: ## Run the test suite
	uv run pytest

raw-table: ## Apply the table definition in sql/raw_spotify_streams.sql
	docker compose exec -T db psql -v ON_ERROR_STOP=1 -U $(POSTGRES_USER) -d $(POSTGRES_DB) < sql/raw_spotify_streams.sql

roles: ## Create layers, roles and grants from sql/roles.sql (needs DBT_PASSWORD and AGENT_PASSWORD)
	@test -n "$(DBT_PASSWORD)" -a -n "$(AGENT_PASSWORD)" || { echo "error: DBT_PASSWORD and AGENT_PASSWORD are required, see .env.example"; exit 2; }
	@docker compose exec -T db psql -v ON_ERROR_STOP=1 -v dbt_password='$(DBT_PASSWORD)' -v agent_password='$(AGENT_PASSWORD)' -U $(POSTGRES_USER) -d $(POSTGRES_DB) < sql/roles.sql

lint-contract: ## Validate the data contract with the Data Contract CLI
	uv run datacontract lint contracts/spotify_streams.odcs.yaml

load: ## Load streaming history into raw.spotify_streams (SOURCE=sample_data)
	uv run python ingest/load.py --source $(or $(SOURCE),sample_data)

inspect: ## Show the structure of an export folder (SOURCE=data)
	@test -n "$(SOURCE)" || { echo "error: SOURCE is required, for example make inspect SOURCE=data"; exit 2; }
	uv run python ingest/inspect_export.py $(SOURCE)
