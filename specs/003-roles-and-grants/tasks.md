---
description: "Task list for Roles and Base Governance (Phase 2)"
---

# Tasks: Roles and Base Governance

**Input**: Design documents from `/specs/003-roles-and-grants/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md). Phases 0 and 1 complete (database up, `uv sync` done, `make test` green).

**Tests**: Included. The spec requires repeatable permission and contract checks (FR-017, FR-018). Tests create throwaway objects with a unique prefix and drop them; they never drop, truncate or alter `raw.spotify_streams` and never call `make raw-table`.

**Organization**: Tasks are grouped by user story. Paths are relative to the repository root `/home/thiago/GitHub/spotify-data-mesh`. Work on branch `003-roles-and-grants`; do not push or merge unless the owner asks.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 to US4 from spec.md
- Language rule (constitution): all code, comments, SQL, YAML and docs in English
- Privacy rule (constitution, principle I): never print, log or commit passwords or field values; tests compare error classes (SQLSTATE `42501`), never error text, because database errors can echo values

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency, settings and Make targets

- [X] T001 Run `uv add --dev datacontract-cli` (updates `pyproject.toml` and `uv.lock`), then `uv sync` and confirm `uv run datacontract --version` prints a version and `uv run dbt --version` still starts with `2.`. If the resolver rejects it, record the conflict in `research.md` (R6) and stop
- [X] T002 [P] Add to `.env.example` two lines `DBT_PASSWORD=change_me_local_only` and `AGENT_PASSWORD=change_me_local_only`, with a comment that they are local-only placeholders and must differ from the owner password in `.env`. Tell the owner to copy the two lines into their own `.env` with values of their choice (do not edit `.env` yourself and do not print it)
- [X] T003 Add to `Makefile` (and to `.PHONY`) three targets, each with a `##` help comment:
  - `roles`: stops with `error: DBT_PASSWORD and AGENT_PASSWORD are required, see .env.example` when either is empty; otherwise `docker compose exec -T db psql -v ON_ERROR_STOP=1 -v dbt_password='$(DBT_PASSWORD)' -v agent_password='$(AGENT_PASSWORD)' -U $(POSTGRES_USER) -d $(POSTGRES_DB) < sql/roles.sql`
  - `psql-agent`: `docker compose exec -e PGPASSWORD=$(AGENT_PASSWORD) db psql -h localhost -U agent -d $(POSTGRES_DB)` (same empty-variable check)
  - `lint-contract`: `uv run datacontract lint contracts/spotify_streams.odcs.yaml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Layers, roles, database-level lockdown and the test harness every story uses

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create `sql/roles.sql` (header comment: what it does, runs as `owner`, idempotent, applied with `make roles`, rerun to rotate passwords) with this first part, in this order:
  1. `\set ON_ERROR_STOP on`
  2. Layers: `CREATE SCHEMA IF NOT EXISTS raw; ... staging; ... marts; ... semantic;` (all owned by the connecting `owner`)
  3. Roles, idempotent: `SELECT 'CREATE ROLE dbt LOGIN' WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbt') \gexec`, the same for `agent`, then `ALTER ROLE dbt LOGIN PASSWORD :'dbt_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;` and the same for `agent` with `:'agent_password'`. Never echo the passwords (no `\echo` of the variables)
  4. Database lockdown: `REVOKE ALL ON DATABASE spotify_mesh FROM PUBLIC;` (use `current_database()` through `\gexec` so the name follows `POSTGRES_DB`), then `GRANT CONNECT ON DATABASE ... TO dbt, agent;` and `GRANT TEMPORARY ON DATABASE ... TO dbt;`. `REVOKE ALL ON SCHEMA public FROM PUBLIC;`
  5. A final `SELECT` that prints one line per layer and role ensured (names only)
- [X] T005 Create `tests/test_roles_db.py` harness (no test bodies yet beyond a smoke test), following the style of `tests/test_load_db.py` (same `.env` reader, skip with a clear reason when the database or the passwords are unreachable or the roles do not exist, message: `run make up and make roles`):
  - fixtures `owner_conn`, `dbt_conn`, `agent_conn` (module scope, `psycopg` with `autocommit=True`, user `owner`/`dbt`/`agent`, passwords from `POSTGRES_PASSWORD`, `DBT_PASSWORD`, `AGENT_PASSWORD`)
  - fixture `raw_table` (module scope): as owner, creates `raw.t_<8 hex chars>` with columns `ts timestamptz, ip_addr inet, conn_country text`, inserts 3 rows using only reserved documentation addresses (`203.0.113.1`, `198.51.100.1`, `192.0.2.1`), yields the name, drops the table at teardown
  - helper `refused(conn, sql)` that returns `True` when the statement raises `psycopg.errors.InsufficientPrivilege` and `False` when it succeeds; any other exception propagates. It never prints or returns the error message
  - smoke test: `dbt_conn` and `agent_conn` can run `select 1`
- [X] T006 Run `make roles` then `uv run pytest tests/test_roles_db.py` until the smoke test passes. `make roles` must print no password

**Checkpoint**: Layers, roles and harness exist - user story work can begin

---

## Phase 3: User Story 1 - The agent role cannot read the IP address (Priority: P1) 🎯 MVP

**Goal**: As `agent`, every read of `raw` and `staging` fails, reads of `marts` and `semantic` work, and nothing can be written or created.

**Independent Test**: As `agent`, `select ip_addr`, `select *` and a read of any staging table all fail with SQLSTATE `42501`; as `owner` the same raw read returns rows (matrix in [contracts/roles-and-grants.md](contracts/roles-and-grants.md)).

- [X] T007 [US1] Add tests to `tests/test_roles_db.py` for the `agent` rows of the matrix (write first, confirm they fail or skip for the right reason before T009): `refused(agent, f"select ip_addr from {raw_table}")`, `select *`, a read of a staging table created by owner for the test, `create table`/`create view` in each of the four layers, `insert`/`update`/`delete`/`truncate`/`drop table` on the raw test table, `create temporary table`, `create role`, `grant select on <raw test table> to agent`; and `not refused` for owner reading `ip_addr` from the same table
- [X] T008 [US1] Add a test that creates a table in `marts` and one in `semantic` as owner, grants nothing, and checks the agent is **refused** (access comes only from default privileges set for `dbt`, see US2); confirms no accidental `PUBLIC` access (FR-009). Drop both at teardown
- [X] T009 [US1] Extend `sql/roles.sql`: `GRANT USAGE ON SCHEMA marts, semantic TO agent;` and no grant at all on `raw` and `staging` to `agent`. Add a comment that the absence of a grant on `raw` and `staging` is the privacy guarantee, not an omission. Re-run `make roles` and `uv run pytest tests/test_roles_db.py` until T007 and T008 pass
- [X] T010 [US1] Run section 2 of [quickstart.md](quickstart.md) by hand with `make psql-agent` and `make psql` against the loaded sample; confirm the three agent reads fail and the owner read returns a count. Record the result in `quickstart.md` under a new heading `## Checkpoint results` (counts and error class only, no values)

**Checkpoint**: The phase's checkpoint passes: as `agent`, `SELECT ip_addr` fails

---

## Phase 4: User Story 2 - The pipeline role can build the layers and nothing more (Priority: P2)

**Goal**: `dbt` reads `raw`, builds in `staging`, `marts` and `semantic`, and cannot modify raw, create roles or grant on raw; agent sees new `marts`/`semantic` objects automatically and never `staging` ones.

**Independent Test**: As `dbt`, create a staging view and a marts table from the raw test table, read both; modify/drop raw, create in raw and grant on raw are all refused; the agent reads the marts table and is refused on the staging view.

- [X] T011 [US2] Add tests to `tests/test_roles_db.py` for the `dbt` rows of the matrix (write first): `not refused` for select on the raw test table, `create view` in `staging`, `create table` and `create or replace`/rebuild (`create table x_new as ...; drop table x; alter table x_new rename to x`) in `marts` and `semantic`; `refused` for insert/update/delete/truncate/drop on the raw test table, `create table` in `raw`, `create role`, `grant select on <raw test table> to agent`, `grant usage on schema raw to agent`. Clean up what dbt created at teardown
- [X] T012 [US2] Add tests for the default privileges: agent `not refused` reading a `dbt`-built marts table, a `dbt`-built semantic view, and a marts table after the rename-replace pattern from T011; agent `refused` on a `dbt`-built staging view
- [X] T013 [US2] Extend `sql/roles.sql` (after the agent grants): `GRANT USAGE ON SCHEMA raw TO dbt;` `GRANT USAGE, CREATE ON SCHEMA staging, marts, semantic TO dbt;` `ALTER DEFAULT PRIVILEGES FOR ROLE owner IN SCHEMA raw GRANT SELECT ON TABLES TO dbt;` `ALTER DEFAULT PRIVILEGES FOR ROLE dbt IN SCHEMA marts, semantic GRANT SELECT ON TABLES TO agent;`. Also grant `SELECT` on tables that already exist now, guarded so it works before the raw table exists: `GRANT SELECT ON ALL TABLES IN SCHEMA raw TO dbt;`. No default privilege for `agent` on `staging`. Comment each statement with why. Re-run `make roles` and the tests until T011 and T012 pass
- [X] T014 [US2] Run section 3 of [quickstart.md](quickstart.md) by hand; add the result (error classes and counts only) under `## Checkpoint results` in `quickstart.md`

**Checkpoint**: `dbt` can run a full build cycle in a later phase and `agent` sees the result with no extra grant

---

## Phase 5: User Story 3 - A data contract classifies every field of the raw stream (Priority: P3)

**Goal**: One ODCS contract lists the 25 fields of `raw.spotify_streams` with a classification each, passes the Data Contract CLI lint, and matches the live table.

**Independent Test**: `make lint-contract` exits 0; `uv run pytest tests/test_contract.py` passes; renaming a property makes the drift test fail naming the field.

- [X] T015 [US3] Create `tests/test_contract.py` (write first) following the rules table in [contracts/spotify-streams-contract.md](contracts/spotify-streams-contract.md): rules 1 (run `uv run datacontract lint`, exit code 0), 4 to 9 (parse with `yaml.safe_load`, no database); rules 2 and 3 (compare with `information_schema.columns` of `raw.spotify_streams`; skip with a reason when the database or the table is missing; failure message names the field and prints only names and type strings). Expected classifications as constants in the test: `ip_addr` restricted, `conn_country` confidential, the other 23 internal
- [X] T016 [US3] Create `contracts/spotify_streams.odcs.yaml` per [data-model.md](data-model.md): ODCS v3 (find the exact `apiVersion` the CLI accepts by running the lint; record it in `research.md` R6), name `spotify_streams`, version `1.0.0`, status `active`, domain `listening`, a description that states: source-aligned, restricted layer, unchanged export rows, the `agent` role has no access, any user agent or username field in a future export is restricted by default. Top-level `roles`: `owner` (access write), `dbt` (access read). Schema object `raw.spotify_streams` with 25 properties in table order, each with `name`, `logicalType`, `physicalType` (PostgreSQL spelling read from `sql/raw_spotify_streams.sql`: `timestamp with time zone`, `inet`, `integer`, `bigint`, `boolean`, `text`), `description`, `classification`, `required: false` (the table has no `NOT NULL` except `loaded_at`, which is `true`). `ip_addr` description gives the reason (direct identifier) and the access rule. The four booleans' descriptions say `null` means unknown, not `false`. No example values from any export
- [X] T017 [US3] Run `make lint-contract` and `uv run pytest tests/test_contract.py` until green. Then prove the drift check: temporarily rename one property in the YAML, confirm the test fails naming that field, revert the rename (`git diff` must show no leftover change)
- [X] T018 [P] [US3] Update `contracts/README.md`: what the contract is, the three classification values with one line each, `make lint-contract`, and that the contracts for `listens` and `listened_catalog` come in Phase 4

**Checkpoint**: Contract lints, matches the table and classifies every field

---

## Phase 6: User Story 4 - Setup is repeatable from nothing (Priority: P3)

**Goal**: From a reset database, setup plus sample load reaches the verified state in one pass; a second run changes nothing; recreating the raw table keeps the permissions.

**Independent Test**: `make reset && make raw-table && make roles && make load && uv run pytest` passes; `make roles` twice passes; `make raw-table` then the permission tests passes without rerunning `make roles`.

- [X] T019 [US4] Add tests to `tests/test_roles_db.py`: (a) idempotency: apply `sql/roles.sql` a second time through `docker compose exec` (skip when `docker` is unavailable) and rerun a representative check; (b) recreation: as owner, drop and recreate the raw test table in `raw`, then `dbt` `not refused` and `agent` `refused`; (c) before-the-table: with the raw test table dropped, `dbt` can read a new one created later (covered by (b)); (d) missing password: `make roles` with `DBT_PASSWORD=` exits non-zero before any change (run through `subprocess`, check exit code and that stdout and stderr do not contain the owner password)
- [X] T020 [US4] Run the full clean sequence from section 1 of [quickstart.md](quickstart.md): `make reset`, `make raw-table`, `make roles`, `make load`, `make test`; then `make roles` again and `make test`; then `make raw-table` and `make test` without `make roles`. All must pass. Time the sequence and record it (SC-003: under 1 minute from `make reset`) under `## Checkpoint results` in `quickstart.md`. Note: `make reset` deletes local database data including any real export loaded; ask the owner before running it, and reload the real export afterwards with `make load SOURCE=data/<folder>` if they want it back
- [X] T021 [P] [US4] Extend `tests/test_repo_hygiene.py` so it also fails when a tracked file contains a line matching `(DBT|AGENT|POSTGRES)_PASSWORD=` followed by a value other than `change_me_local_only` (exclude `Makefile`, which only references `$(...)`). Run it

**Checkpoint**: Setup is repeatable and the guarantee survives raw table recreation

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T022 [P] Update `sql/README.md`: what `roles.sql` and `raw_spotify_streams.sql` do, the order `make raw-table`, `make roles`, `make load`, that `make raw-table` no longer needs a rerun of `make roles`, and the permission matrix in three lines with a link to [contracts/roles-and-grants.md](contracts/roles-and-grants.md)
- [X] T023 [P] Update `README.md`: new `.env` settings, new Make targets, and replace the line "Phase 2 adds database roles..." with the current status; update `docs/architecture.md` status cells for roles, layers and the contract from "Planned, Phase 2" to done, and the layer table. Do not touch the Phase 3 rows
- [X] T024 [P] Mark Phase 2 done in `.claude/plans/implementation-plan.md` with a **Done** line in the style of Phases 0 and 1 (date, what was checked, error class and counts only), and record the two limits found: `dbt` owns what it builds and can grant on it (Phase 4 test guards it), and the agent can see object names in the catalog
- [X] T025 Run `make test`, `make lint-contract` and the section 6 hygiene check of [quickstart.md](quickstart.md); confirm `git status` shows no `.env` and no file under `data/`. Then show the owner the diff summary and wait for them to ask for the commit and push; commits go on branch `003-roles-and-grants`, grouped by concern (setup and SQL, contract, tests, docs)

---

## Dependencies & Execution Order

- **Setup (Phase 1)**: T001 first; T002 and T003 can follow in parallel. T003 depends on nothing else
- **Foundational (Phase 2)**: T004 → T005 → T006. Needs T002 (owner has set passwords) and T003 (`make roles`). Blocks all stories
- **US1 (Phase 3)**: after T006. Tests T007 and T008 before T009. T010 last
- **US2 (Phase 4)**: after T006; independent of US1 in function, but both edit `sql/roles.sql` and `tests/test_roles_db.py`, so run US1 then US2, not in parallel
- **US3 (Phase 5)**: after T001 and the raw table exists (Phase 1 of the project); independent of US1 and US2 (does not need the roles). Can run in parallel with US1 or US2 by a second person since it touches different files
- **US4 (Phase 6)**: after US1 and US2 (it tests their combined result)
- **Polish (Phase 7)**: after all stories; T022, T023, T024 in parallel, T025 last

### Parallel opportunities

- T002 with T003 (different files)
- T018 with T017 (README vs YAML run)
- T021 with T019/T020 (different files)
- T022, T023, T024 together
- US3 as a whole alongside US1/US2

## Implementation Strategy

- **MVP**: Phases 1, 2 and 3. Stopping after T010 already delivers the phase's checkpoint (agent cannot read `ip_addr`)
- **Incremental**: add US2 (`dbt` builds), then US3 (contract), then US4 (repeatability), then docs
- **Safety**: tests use a throwaway raw table, so a database holding the real export is never dropped by the test suite. Only T020 runs `make reset`, and only with the owner's agreement
