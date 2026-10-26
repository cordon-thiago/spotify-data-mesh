# Spotify Data Mesh

A personal data mesh over the Spotify extended streaming history export: Postgres, dbt, ODCS data contracts, a semantic layer and an AI agent, with an eval that compares three agent configurations. The hypothesis is that data contracts and a semantic layer make the agent err less than raw SQL over tables.

The phased plan is in [.claude/plans/implementation-plan.md](.claude/plans/implementation-plan.md), and the business rules in [.claude/plans/business-rules.md](.claude/plans/business-rules.md). This repository is at **Phase 1: raw ingestion**.

## Prerequisites

- **Docker Desktop** with WSL integration enabled for your distro (`docker compose version` must print a version).
- **Python 3.12** (`python3.12 --version`).
- **GNU Make**.
- **libpq5** (`sudo apt install libpq5`): the system library dbt v2 needs to reach Postgres. Needed from Phase 3; install it now.

## Setup

```bash
cp .env.example .env     # local settings; .env is git-ignored
make venv                # create .venv with the pinned dependencies
make up                  # start Postgres and wait until it is healthy
make psql                # open psql inside the container; try: select 1;
```

`.env.example` holds a local-only placeholder password, not a real secret. Change values in `.env`, never in tracked files.

## Make targets

| Target | What it does |
| --- | --- |
| `make help` | List the targets |
| `make venv` | Create `.venv` and install the pinned requirements |
| `make up` | Start the database and wait until it is healthy |
| `make down` | Stop the database; data is kept |
| `make reset` | Delete all database data and start clean |
| `make psql` | Open `psql` inside the database container |
| `make sample` | Generate the synthetic sample data |
| `make test` | Run the test suite |
| `make raw-table` | Create `raw.spotify_streams` from `sql/raw_spotify_streams.sql` |
| `make load` | Load `sample_data/` into the raw table (`SOURCE=data` for the real export) |
| `make inspect SOURCE=data` | Show the structure of an export folder, never its values |

The database listens on `127.0.0.1:5432` only (change `POSTGRES_PORT` in `.env` if the port is taken). Connection settings: user `owner`, database `spotify_mesh`, password from `.env`.

dbt v2 loads the Postgres adapter only with `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true`. The Makefile sets it; if you run `.venv/bin/dbt` by hand, export it first. See [ADR 0001](docs/0001-dbt-v2-experimental-postgres.md).

## Sample data

The pipeline runs on synthetic data with the same 23-field schema as the real export, so you can try everything without your own Spotify data.

```bash
make sample                       # 2000 records, seed 42 (the committed files)
make sample RECORDS=5000 SEED=7   # a different dataset, same schema
make test                         # generator and repository hygiene tests
```

The same `RECORDS` and `SEED` always give byte-identical files. Details, file names and the edge cases every dataset contains are in [sample_data/README.md](sample_data/README.md).

## Loading data

The raw table keeps the export as it arrives (load first, transform later). Its definition is [sql/raw_spotify_streams.sql](sql/raw_spotify_streams.sql); the findings that drove its types are in [docs/real-export-findings.md](docs/real-export-findings.md).

```bash
make raw-table                 # create the schema and table (drops and recreates the table)
make load                      # load sample_data/ (synthetic)
make inspect SOURCE=data       # structure of the real export: names, types, counts
make load SOURCE=data          # load the real export from the private data/ folder
```

`make load` prints, per file and in total, the records read, the rows loaded and the `NULL` counts of the four optional boolean fields, then commits only if every figure matches. A load replaces the table content, is all-or-nothing, and never prints field values. See [ingest/README.md](ingest/README.md).

## Data handling

This repository is public, so what goes into git matters.

| Committed | Never committed |
| --- | --- |
| Code, SQL and dbt models | The real Spotify export (`data/`, except `data/README.md`) |
| Data contracts and eval questions | `.env` (your local settings) |
| Synthetic sample data in `sample_data/` | `.venv/` and local tool settings |

**Why the real export stays out of git:** it contains your IP address and a detailed record of what you listened to and when. Anything pushed to a public repository can be copied, cached and indexed, and deleting it later does not undo that. Synthetic data has the same shape and no personal content, so the pipeline, the tests and the demos use it instead.

**Before each push**, run `make test`. It checks that `data/` is ignored and that no tracked file contains an IPv4 or IPv6 address outside the reserved documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `2001:db8::/32`). It scans the working tree, not the git history; if a real address was ever committed, the history needs to be rewritten before pushing.

## Next phase

Phase 2 adds database roles and grants so the agent can never read restricted fields. See [.claude/plans/implementation-plan.md](.claude/plans/implementation-plan.md).

## Troubleshooting

| Situation | Symptom | Fix |
| --- | --- | --- |
| Docker not reachable from WSL | `docker: command not found`, mentioning WSL integration | Enable WSL integration for your distro in Docker Desktop settings |
| Port already in use | Compose error when binding the port | Set `POSTGRES_PORT` in `.env` to a free port |
| Password unset | `required variable POSTGRES_PASSWORD is missing a value` | `cp .env.example .env` |
| Stale database state | Old tables are still there | `make reset` |
| Wrong Python version | `make venv` stops with `python3.12 not found` | Install Python 3.12 |
| dbt rejects Postgres | `The 'postgres' adapter is not yet supported by dbt` | Set `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true` (the Make targets already do) |
| dbt cannot connect | `libpq.so.5: cannot open shared object file` | `sudo apt install libpq5` |
| `dbt --version` shows `1.x` | An older dbt is in the same environment | Recreate `.venv`; keep only `dbt-oss` |
