---
description: "Task list for Local Development Foundation (Phase 0)"
---

# Tasks: Local Development Foundation

**Input**: Design documents from `/specs/001-local-dev-foundation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The plan defines pytest suites (generator, repository hygiene) as part of the Phase 0 checkpoint. Docker-dependent checks are manual verification tasks. Docker Desktop with WSL integration is available (see plan.md, Open environment findings).

**Organization**: Tasks are grouped by user story. Paths are relative to the repository root `/home/thiago/GitHub/spotify-data-mesh`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, US3 from spec.md
- Language rule (constitution): all code, comments, YAML and docs in English

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repository skeleton and tracked configuration

- [X] T001 Replace the content of `.gitignore` with: `data/*`, `!data/README.md`, `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.claude/settings.local.json`, each under a short English comment (the old plain `data/` line is removed)
- [X] T002 [P] Create `.env.example` with `POSTGRES_USER=owner`, `POSTGRES_PASSWORD=change_me_local_only`, `POSTGRES_DB=spotify_mesh`, `POSTGRES_PORT=5432`, and a comment that the password is a local-only placeholder, not a real secret
- [X] T003 [P] Create `requirements.txt` (`dbt-oss==2.0.8`), `requirements-dev.txt` (`-r requirements.txt`, `pytest==9.1.1`) and `pytest.ini` (`pythonpath = sample_data`, `testpaths = tests`)
- [X] T004 [P] Create one-paragraph English READMEs explaining each folder's purpose and the phase that fills it: `ingest/README.md` (Phase 1), `sql/README.md` (Phase 2), `contracts/README.md` (Phases 2 and 4), `dbt/README.md` (Phase 3)
- [X] T005 [P] Create one-paragraph English READMEs: `agent/README.md` (Phases 5 to 7, configurations A, B, C) and `eval/README.md` (Phases 5 to 8, `questions.yaml`, `expected/`, `reports/`)
- [X] T006 [P] Create `docs/README.md` as the ADR index, listing [docs/0001-dbt-v2-experimental-postgres.md](../../docs/0001-dbt-v2-experimental-postgres.md)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The Python environment and Makefile base that every story uses

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Create `Makefile` with: `SHELL := /bin/bash`, `.PHONY` list, `-include .env` and `export` of its variables, `export DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true`, a `PYTHON ?= python3.12` variable, and the `venv` target that stops with a clear message if `$(PYTHON)` is missing, creates `.venv`, upgrades pip and runs `pip install -r requirements-dev.txt`
- [X] T008 Run `make venv`. If pip rejects a pin in `requirements.txt` or `requirements-dev.txt`, adjust to a resolving version and update the pins in `specs/001-local-dev-foundation/research.md` (section 6) and `contracts/environment-interface.md`. Confirm `.venv` contains `dbt-oss` and no `dbt` or `dbt-core` (`.venv/bin/pip list`)

**Checkpoint**: `.venv` exists with pinned dependencies - user story work can begin

---

## Phase 3: User Story 1 - Bring up the local environment from a clean clone (Priority: P1) 🎯 MVP

**Goal**: A running local database reachable by a command-line client, and a working dbt v2 toolchain, from the README alone.

**Independent Test**: On a clean clone, follow only the README: `cp .env.example .env`, `make up`, `make psql` and run `select 1;`; the connection succeeds. `.venv/bin/dbt --version` starts with `2.`.

### Implementation for User Story 1

- [X] T009 [US1] Create `docker-compose.yml` with service `db`: image `postgres:16`; environment `POSTGRES_USER: ${POSTGRES_USER:-owner}`, `POSTGRES_PASSWORD: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required - run cp .env.example .env}"` (the value MUST be double-quoted and MUST NOT contain `: `, or YAML fails with "mapping values not allowed here" before Compose interpolates it), `POSTGRES_DB: ${POSTGRES_DB:-spotify_mesh}`; ports `127.0.0.1:${POSTGRES_PORT:-5432}:5432`; named volume `pgdata` mounted at `/var/lib/postgresql/data`; healthcheck `pg_isready -U ${POSTGRES_USER:-owner} -d ${POSTGRES_DB:-spotify_mesh}` (interval 5s, retries 12); no `restart` policy. Declare the `pgdata` volume at the bottom
- [X] T010 [US1] Add to `Makefile` the targets `up` (`docker compose up -d --wait`), `down` (`docker compose down`), `reset` (`docker compose down -v` then `docker compose up -d --wait`) and `psql` (`docker compose exec db psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)`), each with a `##` help comment
- [X] T011 [US1] Create `README.md` (English) with: project one-liner and link to `.claude/plans/implementation-plan.md`; prerequisites (Docker Desktop with WSL integration enabled, Python 3.12, GNU Make, `sudo apt install libpq5` for dbt from Phase 3); setup steps (`cp .env.example .env`, `make venv`, `make up`, `make psql`); a Make targets table; a troubleshooting table copied from the failure table in `specs/001-local-dev-foundation/contracts/environment-interface.md` (Docker not reachable, port in use, password unset, stale state, wrong Python, dbt rejects Postgres, `libpq` missing, `dbt --version` shows `1.x`)
- [X] T012 [US1] Verify dbt v2: run `.venv/bin/dbt --version` and confirm the version starts with `2.`
- [X] T013 [US1] Verify quickstart.md section 1: `cp .env.example .env`, `make up`, `make psql` with `select 1;`, create a table, run `make down && make up` and confirm the table still exists with the same user, database and port, then `make reset` and confirm no old tables remain

**Checkpoint**: User Story 1 delivers a reachable database and `dbt` v2; it is the MVP

---

## Phase 4: User Story 2 - Generate synthetic sample data with the real export schema (Priority: P2)

**Goal**: One command produces deterministic synthetic streaming-history files with the 23-field schema and the documented edge cases.

**Independent Test**: Run `make sample` twice; `sha256sum sample_data/*.json` is identical after both runs; each record has all 23 keys; the output contains every edge-case category. `make test` passes the generator tests.

### Tests for User Story 2 (write first, confirm they fail)

- [X] T014 [US2] Create `tests/test_generator.py` covering [contracts/generator-cli.md](contracts/generator-cli.md) and [data-model.md](data-model.md), by running the CLI in a temporary `--out` directory:
  - every record has exactly the 23 keys of the data model in the stated order;
  - exactly one descriptor group is non-null per record (music: fields 6 to 9, podcast: 10 to 12, audiobook: 13 to 16); music and audiobook streams are in the audio file, episodes in the video file;
  - `ms_played` is a positive integer; `ts` parses as UTC and falls in 2024-01-01 to 2025-12-31; `offline_timestamp` is an integer or `null`;
  - `ip_addr` is inside `192.0.2.0/24`, `198.51.100.0/24` or `203.0.113.0/24`;
  - URIs match `spotify:track:<22 base-62>`, `spotify:episode:<22 base-62>`, `spotify:show:<22 base-62>`;
  - determinism: same `--records` and `--seed` give byte-identical files; a different `--seed` gives different content;
  - at `--records 100` the edge cases are present: `null` in each of `shuffle`, `skipped`, `offline`, `incognito_mode` (at least 2 per field), at least 3 `incognito_mode = true`, at least 2 records crossing local midnight in `Europe/Lisbon` in winter and 2 in summer, at least 3 exact duplicates, at least 3 audiobook streams;
  - validation: `--records 0`, `--records 99`, `--records 10000001` and `--records abc` exit with code 2 and the message `error: --records must be between 100 and 10000000`; `--out data` and `--out data/sub` exit with code 2 and `error: refusing to write sample data into data/`

### Implementation for User Story 2

- [X] T015 [US2] Create `sample_data/generate.py` (standard library only): module constants for the 23 field names in order, platform/country/reason value pools, a fixed time window of 2024-01-01 to 2025-12-31 UTC, and builders for music, podcast and audiobook records driven by `random.Random(seed)`. Names are synthetic (`Synthetic Track 0042`, `Synthetic Artist 07`), URIs are `spotify:<kind>:` plus 22 random base-62 characters, `ip_addr` is drawn only from `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`. Random mix about 80% music, 15% podcast, 5% audiobook; about 5% `null` in each of the four booleans; about 3% `incognito_mode = true`; `offline_timestamp` is epoch seconds and not derived from `ts`
- [X] T016 [US2] In `sample_data/generate.py` add the edge-case injectors that always run after the random body: `null` in each optional boolean (at least 2 per field), at least 3 `incognito_mode = true`, at least 2 streams crossing local midnight in `Europe/Lisbon` in winter (UTC offset 0) and 2 in summer (UTC+1) using `zoneinfo`, at least 3 exact duplicates of existing records, at least 3 audiobook streams, and one podcast and one music record whose artist/show strings look alike
- [X] T017 [US2] In `sample_data/generate.py` add the streaming writer and the CLI (`argparse`): options `--records` (default 2000, valid 100 to 10,000,000 inclusive), `--seed` (default 42), `--out` (default `sample_data`, created if missing, refused when it is `data` or inside it); write `streaming_history_audio_sample.json` (music and audiobook) and `streaming_history_video_sample.json` (podcast) one record at a time as a JSON array with `"key" : value` spacing; overwrite existing files; print one line per file with its record count; print the exact error messages and exit with code 2 as in the contract
- [X] T018 [US2] Add to `Makefile` the targets `sample` (`.venv/bin/python sample_data/generate.py --records $(or $(RECORDS),2000) --seed $(or $(SEED),42)`) and `test` (`.venv/bin/pytest`)
- [X] T019 [US2] Run `make test` until `tests/test_generator.py` passes, then run `make sample`, record `sha256sum sample_data/*.json`, run `make sample` again and confirm the checksums are identical (`git status` cannot show this while the files are still untracked); the two generated files in `sample_data/` are the committed fixture
- [X] T020 [P] [US2] Create `sample_data/README.md` explaining that all content is synthetic, how to regenerate (`make sample`, `RECORDS`, `SEED`), the file names and which content type each holds, the injected edge cases, and that real file names are confirmed in Phase 1

**Checkpoint**: User Stories 1 and 2 both work independently

---

## Phase 5: User Story 3 - Understand why raw data stays out of git (Priority: P3)

**Goal**: The owner can state and verify why the real export never enters version control while synthetic data does.

**Independent Test**: Create a dummy file in `data/`; `git status --short data/` lists nothing for it. The README data-handling section answers what is and is not committed, and why. `make test` passes the hygiene tests.

### Tests for User Story 3

- [X] T021 [P] [US3] Create `tests/test_repo_hygiene.py`: (a) `git check-ignore -q data/dummy_export.json` succeeds and `git check-ignore -q data/README.md` fails (it is tracked); (b) scan every file from `git ls-files` plus untracked non-ignored files (`git ls-files --cached --others --exclude-standard`) for IPv4 addresses and fail on any outside `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `127.0.0.0/8`, `0.0.0.0`, the masked `00.000.000.000`; skip `requirements*.txt`; print the offending file and line on failure

### Implementation for User Story 3

- [X] T022 [P] [US3] Create `data/README.md` explaining that this folder holds the real Spotify export, that everything here except this file is ignored by git, and why (IP address, listening habits)
- [X] T023 [US3] Add a "Data handling" section to `README.md` stating what is committed (code, contracts, eval questions, synthetic sample data) and what is never committed (the real export, `.env`), the reason in plain language, and the command to run before each push (`make test`, which includes the IPv4 scan)
- [X] T024 [US3] Run `make test` until `tests/test_repo_hygiene.py` passes; then create `data/export_test.json`, confirm `git status --short data/` lists nothing, and remove the file

**Checkpoint**: All three user stories are independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Completeness checks across stories

- [X] T025 Add to `README.md` a "Sample data" section (commands from T018, link to `sample_data/README.md`) and a "Next phase" pointer to Phase 1 in `.claude/plans/implementation-plan.md`
- [X] T026 Run the full [quickstart.md](quickstart.md) from section 2 to 5 and confirm every expected outcome; section 1 depends on T013
- [X] T027 Final privacy check: `git ls-files` contains no file under `data/` except `data/README.md`, no `.env`, and the IPv4 scan in `make test` passes; `git status` shows no personal data
- [X] T028 Record the outcome: mark the Phase 0 checkpoint as done in `.claude/plans/implementation-plan.md`, and note any unchecked task with its reason in `plan.md` ("Open environment findings")

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies; start immediately.
- **Foundational (Phase 2)**: needs T003 (requirements) and T001; blocks all stories.
- **User Stories (Phases 3 to 5)**: all need Phase 2. US1, US2 and US3 do not depend on each other's code, but several tasks edit the same file (`Makefile`, `README.md`), so those are sequential.
- **Polish (Phase 6)**: after the stories you want delivered.

### Same-file ordering

- `Makefile`: T007 → T010 → T018.
- `README.md`: T011 → T023 → T025.
- `sample_data/generate.py`: T015 → T016 → T017.

### User story dependencies

- **US1 (P1)**: after Phase 2. T013 needs working Docker.
- **US2 (P2)**: after Phase 2. Independent of US1; needs `make test` (T018).
- **US3 (P3)**: after Phase 2. T024 needs the `test` target from T018, so run US2 through T018 first, or add the target earlier.

### Within each story

- Tests (T014, T021) are written first and fail before implementation.
- T014 fails until T017 exists; T021 fails until T001 and T022 are in place.

### Parallel opportunities

- Setup: T002, T003, T004, T005, T006 run together after T001.
- US2: T020 can be written while T015 to T017 are in progress.
- US3: T021 and T022 run together.
- US1 and US2 can proceed in parallel by two people or sessions, if the `Makefile` edits are merged in the order above.

## Parallel Example: Setup

```text
After T001:
Task: "Create .env.example"                       (T002)
Task: "Create requirements*.txt and pytest.ini"   (T003)
Task: "Create ingest/sql/contracts/dbt READMEs"   (T004)
Task: "Create agent/ and eval/ READMEs"           (T005)
Task: "Create docs/README.md"                     (T006)
```

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1 Setup, then Phase 2 Foundational.
2. Phase 3 (US1): database up and `dbt` v2 reporting `2.x`.
3. Stop and validate with the quickstart section 1 (Docker Desktop WSL integration is enabled).

### Incremental delivery

1. Setup and Foundational: the repository is ready.
2. US1: reachable database (MVP).
3. US2: deterministic sample fixture, which Phase 1 of the project (ingestion) consumes.
4. US3: data-handling policy and automated hygiene check.
5. Polish: full quickstart and the final privacy check.

### Notes

- US2 and US3 do not need Docker; only T013 and the first part of T026 do.
- Commit after each phase or logical group; do not commit `.env` or anything under `data/`.
- Phase 0 contains no ✍️ learner tasks.
