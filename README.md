# Spotify Data Mesh

A personal data mesh over the Spotify extended streaming history export: Postgres, dbt, ODCS data contracts, a semantic layer and an AI agent, with an eval that compares three agent configurations. The hypothesis is that data contracts and a semantic layer make the agent err less than raw SQL over tables.

This repository is at **Phase 2b: quality gates**. Next: Phase 3, the dbt staging layer and `fct_listens`.

- Plan: [.claude/plans/implementation-plan.md](.claude/plans/implementation-plan.md) and [business rules](.claude/plans/business-rules.md)
- Architecture: [docs/reference/architecture.md](docs/reference/architecture.md)
- All documentation: [docs/](docs/README.md)

## Prerequisites

- **Docker Desktop** with WSL integration enabled for your distro (`docker compose version` must print a version).
- **Python 3.12** (`python3.12 --version`) and [uv](https://docs.astral.sh/uv/).
- **GNU Make**.
- **libpq5** (`sudo apt install libpq5`): the system library dbt v2 needs to reach Postgres. Needed from Phase 3; install it now.

## Quick start

```bash
cp .env.example .env     # local settings; .env is git-ignored
uv sync                  # create .venv from uv.lock
make hooks               # install the commit-stage checks
make up                  # start Postgres and wait until it is healthy
make sample              # generate synthetic data (2000 records, seed 42)
make raw-table load      # create raw.spotify_streams and load sample_data/
make roles               # layers, roles dbt and agent, grants (set DBT_PASSWORD and AGENT_PASSWORD in .env first)
make psql                # open psql; try: select count(*) from raw.spotify_streams;
```

`.env.example` holds a local-only placeholder password, not a real secret. Change values in `.env`, never in tracked files. The database listens on `127.0.0.1:5432` only (change `POSTGRES_PORT` in `.env` if the port is taken).

## Make targets

| Target | What it does |
| --- | --- |
| `make help` | List the targets |
| `make up` / `make down` | Start the database and wait until healthy / stop it, data kept |
| `make reset` | Delete all database data and start clean |
| `make psql` / `make psql-agent` | Open `psql` as the owner / as the agent role (`SELECT ip_addr` is refused) |
| `make sample` | Generate the synthetic sample data (`RECORDS=`, `SEED=`) |
| `make raw-table` | Create `raw.spotify_streams` from `sql/raw_spotify_streams.sql` (drops and recreates the table) |
| `make load` | Load `sample_data/` into the raw table (`SOURCE=data` for the real export) |
| `make inspect SOURCE=data` | Show the structure of an export folder, never its values |
| `make roles` | Create the layers `staging`, `marts`, `semantic`, the roles `dbt` and `agent`, and the grants |
| `make lint-contract` | Validate the data contract in `contracts/` |
| `make test` | Run the test suite |
| `make hooks` | Install the commit-stage checks (a git pre-commit hook) |
| `make lint` | Run every file check over all tracked files |
| `make scan` | Scan the commits of a range for secrets and IP addresses (`BASE=`, `HEAD=`) |
| `make pr-check` | Run everything the CI workflow runs, on a throwaway database |

Run dbt as `bin/dbt <args>` (a wrapper around `uv run dbt`): dbt v2 loads the Postgres adapter only with `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true`, and the wrapper sets it. See [ADR 0001](docs/adr/0001-dbt-v2-experimental-postgres.md).

## Where to read more

| Topic | Read |
| --- | --- |
| Synthetic data, seeds, edge cases | [sample_data/README.md](sample_data/README.md) |
| Loading, `make load` report, all-or-nothing rule | [ingest/README.md](ingest/README.md) |
| Real export structure (no personal data) | [docs/reference/real-export-findings.md](docs/reference/real-export-findings.md) |
| Roles, grants, why the agent cannot read `raw` | [sql/README.md](sql/README.md), [contracts/README.md](contracts/README.md) |
| Pre-commit checks, CI, allowing a false positive | [docs/guides/quality-gates.md](docs/guides/quality-gates.md) |
| Decisions | [docs/adr/](docs/README.md) |

## Data handling

This repository is public, so what goes into git matters.

| Committed | Never committed |
| --- | --- |
| Code, SQL and dbt models | The real Spotify export (`data/`, except `data/README.md`) |
| Data contracts and eval questions | `.env` (your local settings) |
| Synthetic sample data in `sample_data/` | `.venv/` and local tool settings |

The real export contains your IP address and a detailed record of what you listened to and when. Anything pushed to a public repository can be copied, cached and indexed, and deleting it later does not undo that, so the pipeline, tests and demos use synthetic data with the same shape.

## Quality gates

Checks run before every commit and again on every pull request: a commit that stages a forbidden path, a secret or an IP address is refused. Install once with `make hooks`; run by hand with `make lint`, `make scan` and `make pr-check`. Details, tool install and how to allow a reviewed false positive: [docs/guides/quality-gates.md](docs/guides/quality-gates.md).

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `docker: command not found`, mentioning WSL integration | Enable WSL integration for your distro in Docker Desktop settings |
| Compose error when binding the port | Set `POSTGRES_PORT` in `.env` to a free port |
| `required variable POSTGRES_PASSWORD is missing a value` | `cp .env.example .env` |
| Old tables are still there | `make reset` |
| `uv: command not found` | Install [uv](https://docs.astral.sh/uv/) |
| `The 'postgres' adapter is not yet supported by dbt` | Run dbt as `bin/dbt` (sets `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true`) |
| `libpq.so.5: cannot open shared object file` | `sudo apt install libpq5` |
| `dbt --version` shows `1.x` | `rm -rf .venv && uv sync`; keep only `dbt-oss` in `pyproject.toml` |

Quality-gate errors (`gitleaks is required`, a refused commit) are in [docs/guides/quality-gates.md](docs/guides/quality-gates.md#troubleshooting).
