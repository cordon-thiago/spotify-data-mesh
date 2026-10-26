# Implementation Plan: Raw Ingestion

**Branch**: `002-raw-ingestion` (spec directory only; work stays on `main`) | **Date**: 2026-10-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-raw-ingestion/spec.md`

## Summary

Phase 1 loads the streaming-history JSON files into `raw.spotify_streams`, unchanged. A small Python loader reads one file at a time, renders each value as faithful text, and streams the rows into Postgres with `COPY ... FROM STDIN`, inside one transaction that first empties the table, then checks counts against the source before committing. The table definition is the owner's exercise: the plan fixes only the **conventions** the loader relies on (column names equal to the JSON keys plus a `source_file` column), never the types. A second script inspects the real export and prints structure and counts only, to help write the findings document. Everything runs on the synthetic sample data first, so the checkpoint does not wait for the real ZIP.

## Technical Context

**Language/Version**: Python 3.12 (existing `.venv`)

**Primary Dependencies**: `psycopg[binary]==3.3.6` (new; bundles its own `libpq`, so no system package is needed). Standard library `json`, `argparse`, `pathlib`, `re`. `pytest==9.1.1` for tests (existing).

**Storage**: PostgreSQL 16 from Phase 0, schema `raw`, table `spotify_streams` (definition written by the owner in `sql/raw_spotify_streams.sql`).

**Testing**: pytest. Unit tests need no database. Integration tests use the Phase 0 database and are skipped with a clear reason when it is unreachable. They create their own throwaway schema and table, never the owner's `raw.spotify_streams`.

**Target Platform**: Linux / WSL2, Docker Desktop (as Phase 0)

**Project Type**: Data pipeline tooling (CLI scripts; no service)

**Performance Goals**: Default sample (2,000 records) loads in under 30 s (SC-003). The real export loads in under 10 min (SC-004); streaming `COPY` is expected to reach tens of thousands of rows per second, which is far inside that budget.

**Constraints**: Output and logs contain file names, counts and error categories only (FR-012). A load is all-or-nothing (FR-007). The loader never creates or alters the table (FR-002). One input file in memory at a time (FR-010).

**Scale/Scope**: Sample: 2,000 records in 2 files. Real export: unknown until inspected, likely hundreds of thousands to a few million records in tens of files.

**Open items**: The file-name rule for the real export (FR-011) and any schema differences are unknown until the real ZIP is inspected (US2). The default rule is case-insensitive `streaming_history_*.json`, searched recursively, and is confirmed or corrected after inspection.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Privacy by Permission | PASS | The raw table holds `ip_addr` and is owner-only by construction (only the `owner` user exists until Phase 2). The loader prints no field values and filters database error text, which otherwise echoes values (verified). No intermediate file is written, so nothing with real data can be tracked. |
| II. Contracts as Code | PASS (deferred) | The ODCS contract for `spotify_streams` is Phase 2. This phase writes the conventions the contract will later describe. |
| III. Layered, Tested Transformations | PASS | `raw` is the source layer for dbt staging. Nullable booleans stay nullable. No business rule is applied here. |
| IV. Frozen, Reproducible Eval | PASS (not applicable) | |
| V. Reproducible Without Personal Data | PASS | Pipeline runs on `sample_data/` alone. Tests use synthetic data. The findings document holds structure and counts only and is covered by the IPv4 hygiene scan. |
| VI. Learning-First Phased Delivery | PASS | One concept (source-aligned data, ELT). The column list and types are the owner's ✍️ and are not pre-filled: `sql/raw_spotify_streams.sql` ships as a comment-only stub, and test fixtures use a separate, all-text throwaway table. |
| Technology constraints | PASS | Postgres and Python. `psycopg` is a Python driver, not a new stack layer. English throughout. |
| Quality gates | PASS | `make test` covers the loader; the checkpoint is the count report. |

**Post-design re-check**: unchanged. The design adds one dependency and no violation.

## Project Structure

### Documentation (this feature)

```text
specs/002-raw-ingestion/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── ingest-cli.md
│   └── raw-table-conventions.md
├── checklists/requirements.md
└── tasks.md              # created by /speckit-tasks
```

### Source Code (repository root)

```text
ingest/
├── README.md             # updated: what each script does
├── load.py               # loader (this phase)
└── inspect_export.py     # structure-only report of an export folder
sql/
└── raw_spotify_streams.sql   # OWNER-WRITTEN table definition (comment-only stub until written)
docs/
└── real-export-findings.md   # written by the owner after inspecting the real ZIP (US2)
tests/
├── test_load_unit.py     # no database
└── test_load_db.py       # needs the Phase 0 database; skipped when unreachable
requirements.txt          # + psycopg[binary]==3.3.6
Makefile                  # + raw-table, load, inspect targets
pytest.ini                # pythonpath also includes ingest
```

**Structure Decision**: Two scripts in `ingest/`, both importable so tests exercise functions directly. The table definition lives in `sql/` (as the Phase 2 roles script will), and the findings document in `docs/` next to the ADRs. No new top-level folder.

## Complexity Tracking

No constitution violations to justify.
