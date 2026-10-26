---
description: "Task list for Raw Ingestion (Phase 1)"
---

# Tasks: Raw Ingestion

**Input**: Design documents from `/specs/002-raw-ingestion/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md). Phase 0 complete (database up, `.venv` created, `make test` green).

**Tests**: Included. The plan defines unit and database integration suites as part of the checkpoint. Integration tests use a throwaway schema and an all-`text` fixture table, never `raw.spotify_streams`.

**Organization**: Tasks are grouped by user story. Paths are relative to the repository root `/home/thiago/GitHub/spotify-data-mesh`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1, US2, US3 from spec.md
- **✍️ OWNER**: written by the project owner as a learning exercise. The assistant MUST stop at this task, MUST NOT write the column list or types, and may only explain the data and answer questions (constitution, principle VI)
- **⏸ BLOCKED**: cannot start until the owner has placed the real export ZIP in `data/`
- Language rule (constitution): all code, comments, SQL, YAML and docs in English
- Privacy rule (constitution, principle I): never print, log, paste or commit field values from the real export, only names, counts and types

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependency, stub and Make targets

- [X] T001 [P] Add `psycopg[binary]==3.3.6` to `requirements.txt` and change `pytest.ini` to `pythonpath = sample_data ingest`
- [X] T002 Run `make venv` and confirm `.venv/bin/python -c "import psycopg; print(psycopg.__version__)"` prints `3.3.6` and `.venv/bin/dbt --version` still starts with `2.`. If pip rejects the pin, adjust it and update `research.md` (section 1) and `plan.md`
- [X] T003 [P] Create `sql/raw_spotify_streams.sql` as a **comment-only stub** (no `CREATE` statement, no column names or types). Comments say: this file is written by the owner; create schema `raw` and table `raw.spotify_streams`; one column per JSON field with the same name as the key; plus a `source_file` column; any other column needs a default, identity or generated value; types and constraints are the owner's choice; apply with `make raw-table`; link to `specs/002-raw-ingestion/contracts/raw-table-conventions.md`
- [X] T004 [P] Update `ingest/README.md`: what `load.py` and `inspect_export.py` do (one paragraph each), the Make targets `raw-table`, `load` and `inspect`, that the loader never creates or alters the table, and that output never contains field values
- [X] T005 Add to `Makefile` (and to `.PHONY`) the targets `raw-table` (`docker compose exec -T db psql -v ON_ERROR_STOP=1 -U $(POSTGRES_USER) -d $(POSTGRES_DB) < sql/raw_spotify_streams.sql`), `load` (`$(VENV)/bin/python ingest/load.py --source $(or $(SOURCE),sample_data)`) and `inspect` (stops with `error: SOURCE is required, for example make inspect SOURCE=data/export` when `SOURCE` is empty, else `$(VENV)/bin/python ingest/inspect_export.py $(SOURCE)`), each with a `##` help comment

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure helpers shared by the loader and the inspection script

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create `tests/test_load_unit.py` (no database; write first, confirm it fails) covering the helpers of `ingest/load.py`:
  - `find_files(source, pattern)` returns `(matched, ignored)`: recursive, case-insensitive match of `streaming_history_*.json`, matched in sorted order, paths relative to `source`; a `README.md` and a differently named `.json` land in `ignored`
  - `read_records(path)` returns the list for a valid array, `[]` for an empty array; raises `IngestError` (exit code 2) with exactly `error: invalid JSON in <file> at line L, column C` for malformed JSON and `error: <file> is not an array of records` for a top-level object, an array containing a non-object, or a scalar; the message contains no file content
  - `render(value)`: `None` → `None`; `True` → `"true"`; `False` → `"false"`; `5` → `"5"`; `"abc"` → `"abc"`; `""` → `""` (empty string stays distinct from `None`)
  - `check_keys(record, data_columns, file)` raises `IngestError` (exit code 2) with `error: unknown key <key> in <file>` or `error: missing key <key> in <file>`; passes when the key set equals the data columns exactly
  - `filter_db_error(exc, file)` returns `error: database error in <file>: <ExceptionClass> (SQLSTATE <code>)` and appends `, line L, column <name>` parsed from a context like `COPY t, line 1, column c: "SECRETVALUE"`; the returned text MUST NOT contain `SECRETVALUE`
  - `compare_counts(read, table)` raises `IngestError` (exit code 1) when any per-file or total figure (rows or any of the four boolean `NULL` counts) differs, and returns normally when all match
- [X] T007 Create `ingest/load.py` with the helpers from T006: constants `SOURCE_FILE_COLUMN = "source_file"`, `BOOLEAN_FIELDS = ["shuffle", "skipped", "offline", "incognito_mode"]`, `DEFAULT_PATTERN = "streaming_history_*.json"`, `DEFAULT_TABLE = "raw.spotify_streams"`; class `IngestError(Exception)` carrying an exit code and a one-line message; functions `find_files`, `read_records`, `render`, `check_keys`, `filter_db_error`, `compare_counts`. Messages exactly as listed in T006. Standard library only plus `psycopg` for the error type. One file is read at a time (FR-010)
- [X] T008 Run `.venv/bin/pytest tests/test_load_unit.py` until green

**Checkpoint**: Helpers are tested - user story work can begin

---

## Phase 3: User Story 1 - Load the synthetic sample into the raw table (Priority: P1) 🎯 MVP

**Goal**: One command loads `sample_data/` into the owner's raw table, verified: rows equal records, per file and in total; `NULL` booleans preserved and counted; reload gives the same rows.

**Independent Test**: With the database up and the table applied, `make load` reports `read` equal to `loaded` per file and in total, equal `NULL` counts for `shuffle`, `skipped`, `offline`, `incognito_mode` on both sides, result `committed`; a second `make load` still leaves 2000 rows.

### Tests for User Story 1 (write first, confirm they fail)

- [X] T009 [US1] Create `tests/test_load_db.py`. A fixture reads connection settings from the environment, falling back to parsing `.env`, and calls `pytest.skip("database not reachable: run make up")` when it cannot connect. A second fixture creates schema `test_raw_<random>` with table `spotify_streams` whose columns are the 23 sample field names plus `source_file`, **all of type `text`**, with a comment that this is a throwaway test fixture and not a design for `raw.spotify_streams`, and drops the schema afterwards. Tests run `ingest/load.py` through `subprocess` with `--table test_raw_<random>.spotify_streams` on the sample data generated in a temporary folder (use `sample_data/generate.py --records 100`):
  - rows loaded equal records read, per file and in total; `source_file` holds the relative file name
  - the table-side `NULL` count of each of `shuffle`, `skipped`, `offline`, `incognito_mode` equals the file-side count (the generator guarantees at least 2 per field), and no boolean `NULL` became the text `false` or an empty string
  - exact duplicates in the sample are loaded as they are
  - running the load twice leaves the same row count (not double)
  - table missing: exit code 2 and the output names `sql/raw_spotify_streams.sql` and `make raw-table`; nothing is read
  - `source_file` column missing: exit code 2 and the output names the column
  - a file with an extra key: exit code 2, output names the file and the key, table content unchanged from before the run
  - a file with a missing key: exit code 2, output names the file and the column
  - one valid file plus one malformed JSON file in the same folder: exit code 2 and the table keeps the content of the previous successful load (all-or-nothing)
  - type mismatch (fixture variant with `ms_played integer` and a record whose `ms_played` is the planted marker `"SECRETMARKER9"`): exit code 3, output contains the file name and SQLSTATE, and **does not contain** `SECRETMARKER9`
  - the output of a successful load contains no `Synthetic` string and no `192.0.2.`/`198.51.100.`/`203.0.113.` address (only names and counts)

### Implementation for User Story 1

- [X] T010 [US1] In `ingest/load.py` add `connect()` (settings from `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`, optional `POSTGRES_HOST` defaulting to `127.0.0.1`; a missing password raises `IngestError` exit code 2 with `error: POSTGRES_PASSWORD is not set - run cp .env.example .env`) and `inspect_table(conn, table)` that reads `information_schema.columns` and returns the **data columns** (columns with `column_default IS NULL`, `is_identity = 'NO'`, `is_generated = 'NEVER'`, excluding `source_file`) in table order. Missing table raises `IngestError` exit code 2: `error: table <table> not found - write sql/raw_spotify_streams.sql and run make raw-table`; missing `source_file` raises `error: column source_file missing in <table>`. Table names are quoted as identifiers, never interpolated as raw text
- [X] T011 [US1] In `ingest/load.py` add `load_files(conn, table, source, files, data_columns)`: inside one transaction run `TRUNCATE <table>`, then for each file `read_records`, `check_keys` every record, and stream rows with `cursor.copy("COPY <table> (<data columns>, source_file) FROM STDIN")` and `write_row([render(record[c]) for c in data_columns] + [relative path])`; count, per file, records read and `None` values in each of `BOOLEAN_FIELDS`. Any `psycopg.Error` becomes an `IngestError` with exit code 3 through `filter_db_error`. Records are never modified, trimmed or validated for meaning (FR-003)
- [X] T012 [US1] In `ingest/load.py` add `table_counts(conn, table, files)` (per `source_file`: `count(*)` and `count(*) FILTER (WHERE <field> IS NULL)` for each boolean field), the report printer (format as in `contracts/ingest-cli.md`: per file, `TOTAL`, `ignored:` list, `result:`; when a null count differs print `file/table`), and `main()` with `argparse` options `--source` (default `sample_data`), `--pattern` (default `DEFAULT_PATTERN`), `--table` (default `DEFAULT_TABLE`). Order: connect, `inspect_table`, `find_files` (exit 2 `error: no files matching <pattern> found in <source>` when none), `load_files`, `table_counts`, `compare_counts` then `COMMIT`; on any `IngestError` or exception `ROLLBACK` and exit with its code (`error: counts differ, load rolled back` for code 1). stdout carries the report, stderr the error line; no field values anywhere
- [X] T013 [US1] Run `make test` until `tests/test_load_unit.py` and `tests/test_load_db.py` pass (the database must be up: `make up`). Then run `make load` while `sql/raw_spotify_streams.sql` is still the comment-only stub and confirm exit code 2 with the message naming `sql/raw_spotify_streams.sql` and `make raw-table`
- [X] T014 [US1] ✍️ OWNER (written by the assistant at the owner's explicit request, with each type explained in comments): write the table definition in `sql/raw_spotify_streams.sql`: `CREATE SCHEMA IF NOT EXISTS raw;` and `CREATE TABLE raw.spotify_streams (...)` with one column per JSON field (same names as the keys, listed in [data-model.md of Phase 0](../001-local-dev-foundation/data-model.md)) plus `source_file`, choosing every type yourself (think about how to keep `null`, `false` and `true` apart in the four boolean fields, what `ts` and `offline_timestamp` should be, and what is safe for `ip_addr`). Make the file re-runnable (for example `DROP TABLE IF EXISTS` first). The assistant MUST NOT write the columns or types; it may explain the data and review the result when asked
- [X] T015 [US1] Run `make raw-table`, then `make load`, and verify quickstart.md section 2 against the owner's table: the report's per-file and total counts match; the same counts and `NULL` counts from `make psql` (`select source_file, count(*) ...`); a second `make load` leaves 2000 rows; result `committed`. If the load fails because the owner's types do not fit the data, show the owner the file, line and column from the error and let the owner fix the definition

**Checkpoint**: User Story 1 works on its own and meets the Phase 1 checkpoint for the sample data. This is the MVP

---

## Phase 4: User Story 2 - Inspect the real export and record what it contains (Priority: P2)

**Goal**: The structure of the real export is known and written down, without any personal data, and the file rule, table definition and generator are aligned with it.

**Independent Test**: `docs/real-export-findings.md` lists every streaming-history file pattern with record count and content type, every schema difference and the excluded files, and passes the IPv4 hygiene scan.

### Tests for User Story 2

- [X] T016 [P] [US2] Create `tests/test_inspect_export.py` (no database): generate a dataset with `sample_data/generate.py --records 100` into a temporary folder and run `ingest/inspect_export.py` on it. Assert: the report lists both files with record counts equal to the generated counts; for the keys `shuffle` and `incognito_mode` it shows how many records have the key, the JSON types seen (`boolean`, `null`) and the null count; a folder with an extra key added to one record reports that key as outside the 23 sample fields, and a record without a key reports the field as absent; content-type groups are counted per file (music, podcast, audiobook, none, several); a non-matching file is listed as ignored; the output contains no `Synthetic` string and no documentation-range IP address; exit code 2 with the loader's invalid-JSON message for a malformed file

### Implementation for User Story 2

- [X] T017 [US2] Create `ingest/inspect_export.py` (`python ingest/inspect_export.py DIR [--pattern GLOB]`) importing `find_files`, `read_records` and `IngestError` from `ingest/load.py`. For each matching file print: path, record count, and per JSON key the number of records having it, the JSON value types seen (`string`, `number`, `boolean`, `null`, `object`, `array`) and the null count; then the keys outside the 23 sample fields, the sample fields that are absent, and per file the number of records filling each descriptor group (music: `master_metadata_track_name`, `master_metadata_album_artist_name`, `master_metadata_album_album_name`, `spotify_track_uri`; podcast: `episode_name`, `episode_show_name`, `spotify_episode_uri`; audiobook: `audiobook_title`, `audiobook_uri`, `audiobook_chapter_uri`, `audiobook_chapter_title`), counted as none or several when zero or more than one group is filled; list ignored files; print the size in MB of each file. Names, counts and types only, never values; exit code 0, or 2 on input errors
- [X] T018 [US2] Run `.venv/bin/pytest tests/test_inspect_export.py` until green, then `make inspect SOURCE=sample_data` and read the output to confirm it shows no values
- [X] T019 [US2] ⏸ BLOCKED, OWNER: place the real export ZIP in `data/` and extract it into `data/export/` (for example `unzip data/<file>.zip -d data/export`). Confirm `git status --short` shows nothing for `data/`
- [X] T020 [US2] ⏸ BLOCKED: run `make inspect SOURCE=data/export` and review the structure-only output with the owner (do not open or print any real JSON file)
- [X] T021 [US2] ⏸ BLOCKED: write `docs/real-export-findings.md` (English; structure and counts only; no track, artist, episode or show names, no IP address, no username) with sections Files (name pattern, record count and content type for each streaming-history file), Excluded (files not loaded and why), Schema (fields added, missing or of a different JSON type than the 23-field sample schema), Size (total records, largest file in MB, whether `json.load` per file is safe), Decisions (what must change). Add the file to the docs index in `docs/README.md`
- [X] T022 [US2] ⏸ BLOCKED: apply the decisions of T021: if the real file names do not match `streaming_history_*.json` change `DEFAULT_PATTERN` in `ingest/load.py` and its test; if the schema differs update `sample_data/generate.py`, `tests/test_generator.py` and `specs/001-local-dev-foundation/data-model.md`; ask the owner to update `sql/raw_spotify_streams.sql` (✍️) and re-run `make raw-table`. If nothing differs, write "no changes needed" in the Decisions section. Run `make test`

**Checkpoint**: The real export is described and the project matches it

---

## Phase 5: User Story 3 - Load the real export without ever committing it (Priority: P3)

**Goal**: The real export is in the raw table, verified, with nothing from it in version control, logs or console output.

**Independent Test**: `make load SOURCE=data/export` reports equal counts and `NULL` counts, result `committed`; the output has names and counts only; `git status` and `make test` show no real data in tracked files.

- [X] T023 [US3] ⏸ BLOCKED: after T022, run `make load SOURCE=data/export` (time it) and compare the report with the counts in `docs/real-export-findings.md`: per-file and total rows equal, `NULL` counts of the four booleans equal on both sides, result `committed`. Run it a second time and confirm the row count is unchanged
- [X] T024 [US3] ⏸ BLOCKED: privacy check after the real load: the console output of T023 contained only file names and counts; `git status --short` lists nothing from `data/`; `make test` (including the IPv4 hygiene scan) passes; `git log -p --all` has no IPv4 address outside the allowed ranges; no file with real values exists outside `data/`
- [X] T025 [US3] ⏸ BLOCKED: record in `docs/real-export-findings.md` the total rows loaded and the load time (SC-004), without any value; if the load exceeded 10 minutes or the memory use was a problem, note the cause and the option (streaming parser) for the next iteration

**Checkpoint**: All three user stories are complete

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T026 Update `README.md`: add `make raw-table`, `make load` and `make inspect` to the Make targets table; add a "Loading data" section (apply your table definition, `make load` for the sample, `make load SOURCE=data/export` for the real export, what the report shows, that a load replaces the table content and is all-or-nothing); update "Next phase" to point to Phase 2
- [X] T027 Run quickstart.md sections 1 to 3 and 6 for the sample data and time `make load` (SC-003: under 30 s). Sections 4 and 5 are run only once T019 is unblocked
- [X] T028 Mark the Phase 1 checkpoint in `.claude/plans/implementation-plan.md`: done for the sample data after T015, and for the real export after T023. List every unchecked ⏸ BLOCKED task in the "Open items" of `specs/002-raw-ingestion/plan.md` with the action the owner must take (place the ZIP in `data/`)

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: needs T001 and T002; blocks all stories.
- **US1 (Phase 3)**: needs Phase 2. T014 (✍️) needs the owner; T015 needs T012 and T014.
- **US2 (Phase 4)**: T016 to T018 need only Phase 2 (the inspection reuses `read_records`). T019 to T022 are blocked until the real ZIP exists.
- **US3 (Phase 5)**: needs T022 and a working owner table (T014, T015).
- **Polish (Phase 6)**: T026 and T027 after US1; T028 last.

### Same-file ordering

- `ingest/load.py`: T007 → T010 → T011 → T012 (then T022 if the file rule changes).
- `Makefile`: T005 only in this phase.
- `README.md`: T026. `docs/README.md`: T021.

### User story dependencies

- **US1 (P1)**: independent of the real export; the MVP.
- **US2 (P2)**: its code (T016 to T018) is independent of US1; its real-data part is blocked on the ZIP.
- **US3 (P3)**: depends on US1 and on US2's findings.

### Within each story

- Tests first (T006, T009, T016), confirm they fail, then implement.
- T013 before T014: first prove the loader refuses a missing table, then let the owner write the definition.

### Parallel opportunities

- Setup: T001, T003 and T004 together.
- US2's T016 can be written while US1 is implemented (different files).
- The owner can write the definition (T014) while T016 to T018 are done.

## Parallel Example: Setup

```text
Together:
Task: "Add psycopg to requirements.txt and extend pytest.ini"   (T001)
Task: "Create comment-only sql/raw_spotify_streams.sql stub"    (T003)
Task: "Update ingest/README.md"                                 (T004)
```

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 1 Setup, Phase 2 Foundational.
2. Phase 3 (US1): tested loader, then the owner writes the table definition, then load and verify the sample data.
3. Stop and validate the Phase 1 checkpoint on the sample data (quickstart sections 1, 2, 3 and 6). Nothing here needs the real ZIP.

### Incremental delivery

1. US1: the load path and the checkpoint on synthetic data.
2. US2 code: the inspection script, tested on the sample data. When the ZIP arrives: findings and alignment.
3. US3: the real load and the privacy check.
4. Polish: README and plan status.

### Notes

- Stop at T014 and hand over to the owner. If the owner asks for help, explain the fields, the Postgres types and their trade-offs, but do not write the column list.
- Do not run `make load SOURCE=data/...`, open real JSON files or paste real output into the conversation before T019 is done and the owner agrees.
- Commit after each phase or logical group; never commit anything under `data/` (except its README) or `.env`.
