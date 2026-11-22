SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help up down reset psql psql-agent sample test raw-table roles lint-contract load inspect hooks lint scan pr-check test-ci

# Load local settings (POSTGRES_*) from ENV_FILE (default .env) when it exists, and pass them to every command.
# make pr-check selects .env.ci (throwaway credentials) so it never touches the owner's database.
ENV_FILE ?= .env
-include $(ENV_FILE)
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

# Prerequisite check for the quality-gate targets: a clear one-line message and exit 2, not a stack trace.
NEED_PRECOMMIT = command -v uv >/dev/null 2>&1 || { echo "error: uv is required, see README (Troubleshooting)"; exit 2; }; \
	uv run --no-sync pre-commit --version >/dev/null 2>&1 || { echo "error: run uv sync first"; exit 2; }

hooks: ## Install the commit-stage checks (pre-commit hook)
	@$(NEED_PRECOMMIT)
	uv run pre-commit install

lint: ## Run every file check over all tracked files
	@$(NEED_PRECOMMIT)
	SKIP=gitleaks uv run pre-commit run --all-files --show-diff-on-failure

scan: ## Scan the commits of a range for secrets and IP addresses (BASE=, HEAD=)
	@command -v gitleaks >/dev/null 2>&1 || { echo "error: gitleaks is required, see README (Quality gates)"; exit 2; }
	@base="$(or $(BASE),origin/main)"; head="$(or $(HEAD),HEAD)"; \
	if [[ "$$base" =~ ^0+$$ ]]; then range="-1 $$head"; else range="$$base..$$head"; fi; \
	echo "scanning commits: $$range"; \
	gitleaks git --redact --no-banner --log-opts="$$range" .

# Everything the CI workflow runs, on a throwaway database: its own compose project (smesh-ci), port 55432 and
# generated credentials in .env.ci. It never calls reset or down and never mounts the owner's volume.
pr-check: ## Run everything the CI workflow runs, on a throwaway database (BASE=, HEAD=)
	@$(NEED_PRECOMMIT)
	@docker info >/dev/null 2>&1 || { echo "error: Docker is not reachable, see README (Troubleshooting)"; exit 2; }
	$(MAKE) lint
	$(MAKE) scan BASE="$(BASE)" HEAD="$(HEAD)"
	@set -euo pipefail; \
	cleanup() { docker compose -p smesh-ci --env-file .env.ci down -v >/dev/null 2>&1 || true; rm -f .env.ci; }; \
	trap cleanup EXIT; \
	owner_pw=$$(openssl rand -hex 16); dbt_pw=$$(openssl rand -hex 16); agent_pw=$$(openssl rand -hex 16); \
	if [ "$${GITHUB_ACTIONS:-}" = "true" ]; then \
		for v in "$$owner_pw" "$$dbt_pw" "$$agent_pw"; do echo "::""add-mask::$$v"; done; \
	fi; \
	printf '%s\n' POSTGRES_USER=owner POSTGRES_DB=spotify_mesh POSTGRES_PORT=55432 COMPOSE_PROJECT_NAME=smesh-ci \
		"POSTGRES_PASSWORD=$$owner_pw" "DBT_PASSWORD=$$dbt_pw" "AGENT_PASSWORD=$$agent_pw" > .env.ci; \
	$(MAKE) up raw-table roles load SOURCE=sample_data ENV_FILE=.env.ci; \
	rc=0; out=$$($(MAKE) test-ci ENV_FILE=.env.ci 2>&1) || rc=$$?; printf '%s\n' "$$out"; \
	if [ "$$rc" -ne 0 ]; then exit "$$rc"; fi; \
	if printf '%s\n' "$$out" | grep -q '^SKIPPED'; then \
		echo "error: a test was skipped, so the database setup is broken (see the SKIPPED lines above)"; exit 1; \
	fi

# Used by pr-check only: the same suite as `make test`, with the skip reasons printed.
test-ci:
	uv run pytest -rs
