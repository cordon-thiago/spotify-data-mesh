# Research: Raw Ingestion

All Technical Context unknowns are resolved below. Two claims were verified against the running Phase 0 database with `psycopg` 3.3.6 (section 2 and 7).

## 1. Database driver

- **Decision**: `psycopg[binary]==3.3.6` (psycopg 3), added to `requirements.txt`.
- **Rationale**: The `binary` extra bundles `libpq`, so it works without the system package that dbt needs. psycopg 3 has first-class `COPY ... FROM STDIN` support with row-by-row writing.
- **Alternatives**: `psycopg2` (older API, COPY needs a file-like object); `asyncpg` (async not needed); shelling out to `psql \copy` (needs a CSV on disk, hides counts and errors).

## 2. Loading mechanism: stream rows into `COPY`, no CSV file

- **Decision**: Open `COPY <table> (<columns>) FROM STDIN` and call `write_row()` per record. No CSV file is written.
- **Rationale**: Same bulk-load speed as the CSV route, and it removes the intermediate file that could hold real data on disk (FR-013). Verified: `None` is stored as `NULL`, an empty string stays an empty string, so `null` and `''` stay distinguishable.
- **Departure from the plan text**: the original plan says "JSON → CSV → COPY". The concept taught (bulk `COPY`, load first, transform later) is unchanged; only the CSV step is dropped. The requirement in the spec is about outcomes, not CSV.
- **Alternatives**: Write a CSV in `data/` then `COPY ... FROM STDIN` (an extra file with real data, plus the NULL-versus-empty-string ambiguity of CSV); `INSERT` per row (orders of magnitude slower); `executemany` (still slow).

## 3. How values are sent: faithful text, Postgres converts

- **Decision**: Render each JSON value as its JSON-faithful text and let Postgres convert by column type: `null` → `None` (SQL `NULL`), `true`/`false` → `'true'`/`'false'`, numbers → their decimal text, strings unchanged.
- **Rationale**: The loader then never needs to know the column types the owner chose. A boolean column receives `'true'` and parses it; a text column stores `true` exactly as the source said. Verified: `'true'` loads into `boolean` correctly.
- **Consequence**: A value that does not fit the owner's column type (for example `'abc'` into an integer column) makes `COPY` fail, which rolls back the whole load and names the file (FR-007, FR-009). That is the intended signal that the table definition does not match the data.
- **Alternatives**: Convert in Python by a hard-coded type map (would pre-fill the owner's type decisions); send native Python types (`bool` becomes `t`/`f`, which would store `t` in a text column and not be source-faithful).

## 4. Table definition stays the owner's

- **Decision**: `sql/raw_spotify_streams.sql` ships as a comment-only stub explaining what to write. The loader and the plan state only **conventions**: one column per JSON field with the same name, plus a `source_file` column, in schema `raw`, table `spotify_streams`. Types, nullability, constraints and extra columns are the owner's choice.
- **Rationale**: The implementation plan marks the column list and types as ✍️, and constitution principle VI forbids pre-filling it. Column **names** are not a free choice (they come from the source) so they can be fixed without taking the exercise away.
- **Test fixtures**: Tests create a throwaway table in a temporary schema with all-`text` columns. That table exists to test the loader mechanics, is not a recommended design, and is dropped after each test.
- **Alternatives**: Ship a complete DDL (violates the ✍️); have the loader create the table (violates FR-002 and the exercise).

## 5. Which columns the loader loads

- **Decision**: The loader reads the target table's columns from `information_schema.columns`. **Data columns** are those without a default, not identity and not generated, excluding `source_file`. Every record's key set must equal the data-column set exactly. Columns with a default, identity or generated (for example a row id or a load timestamp) are left to the database. `source_file` must exist and is set by the loader.
- **Rationale**: Drives the loader from the owner's table instead of a hard-coded list, so the loader follows schema findings from the real export without code changes. Exact equality detects both a new field in the export and a missing one (FR-009).
- **Alternatives**: Hard-coded 23-field list in the loader (breaks when the real export differs and duplicates the generator's list).

## 6. Source-file traceability

- **Decision**: `source_file` holds the file path relative to the chosen source folder (for example `Spotify Extended Streaming History/Streaming_History_Audio_2024_0.json` or `streaming_history_audio_sample.json`).
- **Rationale**: Enables per-file counts (FR-005, FR-006) without extra tables. Relative paths contain no personal data.
- **Alternatives**: File name only (ambiguous if two folders hold the same name); a separate load-log table (more design than this phase needs).

## 7. Errors without values

- **Decision**: Catch `psycopg.Error` and print only the file name, the exception class, the SQLSTATE and, when present, the COPY line and column name parsed from `diag.context` with a regular expression. Never print `message_primary`, `message_detail` or `context` directly.
- **Rationale**: Verified: for `'SECRETVALUE'` into an integer column, `message_primary` is `invalid input syntax for type integer: "SECRETVALUE"` and `context` is `COPY t, line 1, column c: "SECRETVALUE"`; `diag.column_name` is empty. Printing either would leak the value, which for this table can be an IP address. Same rule for JSON decode errors: print the file name and the position (line and column), not the surrounding text.
- **Alternatives**: Print the raw database error (leaks values); suppress all detail (undiagnosable).

## 8. All-or-nothing, re-runnable load, verified before commit

- **Decision**: One transaction: `TRUNCATE` the target table, `COPY` every file, then query per-file row counts and `NULL` counts of the four optional booleans from the table, compare with the counts taken while reading, and `COMMIT` only if every pair matches; otherwise `ROLLBACK` and exit 1.
- **Rationale**: Delivers FR-006, FR-007 and FR-008 together: a failed or mismatched run leaves the previous content; a successful rerun equals a single run. Verifying before the commit means a wrong count can never become the table's content.
- **Alternatives**: Append with a load id and delete-by-id (more design, appending is out of scope); `DELETE` instead of `TRUNCATE` (slower, no benefit; TRUNCATE is transactional in Postgres).

## 9. Reading JSON files

- **Decision**: Standard-library `json.load` for one file at a time, validate that the top level is a list of objects, release the file before the next one.
- **Rationale**: Export files are split by period and are tens of megabytes at most; one file at a time satisfies FR-010 with no extra dependency. The risk (a single file that does not fit in memory) is recorded and checked against the file sizes during inspection.
- **Alternatives**: `ijson` streaming parser (extra dependency, only needed if inspection finds a huge single file).

## 10. File discovery rule

- **Decision**: Search the source folder recursively for files whose name matches `streaming_history_*.json`, case-insensitively, in sorted order. Every other file found is listed as ignored. The rule is overridable with `--pattern` and is confirmed against the real export in US2.
- **Rationale**: The sample files and the known real naming (`Streaming_History_Audio_...`, plus the `Video` file the owner reported) both match. The ZIP extracts into a subfolder, hence recursive search.
- **Alternatives**: Load every `*.json` (would pick up account-data files with another schema); list files in configuration (more setup for little gain).

## 11. Inspection script

- **Decision**: `ingest/inspect_export.py <folder>` prints, per matching file, the record count, the set of JSON keys with how many records have each, the JSON value types seen per key, and the null count per key; it flags keys outside the expected 23 and which of the three descriptor groups each file contains. It prints names, counts and types only.
- **Rationale**: Supports US2 and the findings document (FR-014) without exposing values; safe to run on the real export.
- **Alternatives**: Ad-hoc `jq` (not installed, and easy to print values by accident); manual inspection of the real files (risks screenshots or pastes of personal data).

## 12. Findings document

- **Decision**: `docs/real-export-findings.md`, written by the owner after running the inspection, containing structure and counts only. The hygiene test already scans tracked files for IPv4 addresses.
- **Alternatives**: Keep the findings inside `data/` (never versioned, so not reviewable); put them in the spec (mixes design with discovered facts).

## 13. Command surface

- **Decision**: New Make targets: `raw-table` (runs `sql/raw_spotify_streams.sql` in the container), `load` (`SOURCE=sample_data` by default) and `inspect` (`SOURCE` required). Database settings come from `.env` through the Makefile.
- **Rationale**: Same surface as Phase 0. `raw-table` keeps the owner's DDL runnable without remembering a `psql` invocation.
- **Alternatives**: Run DDL by hand each time (error-prone); apply DDL inside the loader (violates FR-002).

## 14. Test strategy

- **Decision**: Unit tests (no database) for file discovery, record validation, text rendering and the error filter. Integration tests (skipped when Postgres is unreachable) for load, counts, null preservation, idempotent reload, rollback on a bad file, missing table, and the no-values-in-output rule, each on a throwaway schema.
- **Rationale**: Keeps `make test` useful on a machine without Docker running while still proving the checkpoint when it is.
- **Alternatives**: Mock the database (does not prove `COPY` behaviour, the most failure-prone part); require the database for every test (breaks the Phase 0 promise that tests run without Docker).
