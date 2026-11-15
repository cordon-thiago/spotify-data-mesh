# Implementation Plan: Roles and Base Governance

**Branch**: `003-roles-and-grants` | **Date**: 2026-11-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-roles-and-grants/spec.md`

## Summary

Phase 2 makes the privacy rule a database fact. One idempotent SQL script (`sql/roles.sql`), applied with `make roles`, creates the layers `staging`, `marts` and `semantic` (next to the existing `raw`), the login roles `dbt` and `agent`, and the grants. Access is by layer: `agent` has no grant on `raw` or `staging` at all and read-only access to `marts` and `semantic`; `dbt` reads `raw` and builds in the other three. Default privileges make new `raw` tables readable by `dbt` and new `dbt`-built tables in `marts` and `semantic` readable by `agent`, so nothing is re-granted per object and recreating the raw table needs no extra step. A data contract (`contracts/spotify_streams.odcs.yaml`) classifies every field. Tests connect as each real role and assert the exact errors; a drift test compares the contract with the live table. Everything runs on sample data.

## Technical Context

**Language/Version**: Python 3.12 (existing); SQL (PostgreSQL 16 dialect)

**Primary Dependencies**: `psycopg[binary]==3.3.6` (existing). New dev dependency: `datacontract-cli` (resolves cleanly with the existing lock, 47 packages; version pinned by `uv add --dev`). `pyyaml` arrives with it and is used by the drift test.

**Storage**: PostgreSQL 16, database `spotify_mesh`; schemas `raw` (exists), `staging`, `marts`, `semantic` (new).

**Testing**: pytest. `tests/test_roles_db.py` (needs the database and the roles; skipped with a reason otherwise) and `tests/test_contract.py` (lint, classification rules; drift part needs the database). Tests create throwaway objects with a unique prefix and drop them; they never drop or alter `raw.spotify_streams`.

**Target Platform**: Linux / WSL2, Docker Desktop (as before)

**Project Type**: Data platform setup (SQL script, contract file, tests; no service)

**Performance Goals**: `make roles` finishes in under 10 s on a fresh database; full phase from `make reset` to verified in under 1 minute (SC-003).

**Constraints**: No password in the repository (FR-011). Output shows role names, counts and error classes only (FR-019). Setup is idempotent (FR-010).

**Scale/Scope**: 3 roles, 4 layers, 1 contract with 25 properties (23 export fields plus `source_file` and `loaded_at`).

**Open items resolved in research.md**: how passwords reach the script, how default privileges behave for tables, views and replaced tables, what `PUBLIC` holds by default in PostgreSQL 16, contract format fields, how the drift check maps types.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Privacy by Permission | PASS | This phase is the principle's implementation: `agent` has no grant on `raw`/`staging`, so even `SELECT *` and future columns are refused. Limits stated, not hidden: `dbt` owns what it builds and could expose `ip_addr` in a mart; Phase 4 test is the guard. Row limit and audit log are Phase 6 (Principle I covers them for the agent, which does not exist yet). |
| II. Contracts as Code | PASS | `spotify_streams` ODCS contract with a classification on every property, linted by the Data Contract CLI. The CI test for restricted fields in marts is Phase 4 and Phase 2b. |
| III. Layered, Tested Transformations | PASS | Creates the layers dbt will use; no model yet. |
| IV. Frozen, Reproducible Eval | PASS (not applicable) | |
| V. Reproducible Without Personal Data | PASS | Tests and quickstart run on `sample_data/`. Passwords from git-ignored `.env`; `.env.example` holds placeholders only. |
| VI. Learning-First Phased Delivery | PASS | One concept (privacy by permission). No ✍️ part in this phase's plan section, so the assistant writes the script. Complexity beyond the phase (CI, pre-commit) is deliberately deferred to Phase 2b. |
| Technology constraints | PASS | Postgres, ODCS, Data Contract CLI as the constitution lists. English throughout. |
| Quality gates | PASS | `make test` covers permissions and the contract. |

**Post-design re-check**: unchanged; one new dev dependency, no violation.

## Project Structure

### Documentation (this feature)

```text
specs/003-roles-and-grants/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── roles-and-grants.md          # the permission matrix the tests assert
│   └── spotify-streams-contract.md  # rules the contract file must satisfy
├── checklists/requirements.md
└── tasks.md                         # created by /speckit-tasks
```

### Source Code (repository root)

```text
sql/
├── roles.sql                          # layers, roles, grants; idempotent
└── README.md                          # updated
contracts/
├── spotify_streams.odcs.yaml          # ODCS contract, classification per property
└── README.md                          # updated
tests/
├── test_roles_db.py                   # connects as owner, dbt, agent
└── test_contract.py                   # lint, classification rules, drift vs table
.env.example                           # + DBT_PASSWORD, AGENT_PASSWORD (placeholders)
Makefile                               # + roles, lint-contract, psql-agent targets
pyproject.toml / uv.lock               # + datacontract-cli (dev)
docs/architecture.md, README.md        # status updates
```

**Structure Decision**: Follows the plan's folder conventions (`sql/`, `contracts/`). One SQL file, not one per role: order matters (schemas, roles, grants, default privileges) and one idempotent file is easier to read and rerun.

## Complexity Tracking

No constitution violations to justify.
