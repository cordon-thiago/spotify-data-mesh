# Spotify Data Mesh

A personal data mesh over the Spotify extended streaming history export: Postgres, dbt, ODCS data contracts, a semantic layer and an AI agent, with an eval that compares three agent configurations. The hypothesis is that data contracts and a semantic layer make the agent err less than raw SQL over tables.

The phased plan is in [.claude/plans/implementation-plan.md](.claude/plans/implementation-plan.md), and the business rules in [.claude/plans/business-rules.md](.claude/plans/business-rules.md). The architecture is described in [docs/architecture.md](docs/architecture.md). This repository is at **Phase 2b: quality gates**.

## Prerequisites

- **Docker Desktop** with WSL integration enabled for your distro (`docker compose version` must print a version).
- **Python 3.12** (`python3.12 --version`).
- **GNU Make**.
- **libpq5** (`sudo apt install libpq5`): the system library dbt v2 needs to reach Postgres. Needed from Phase 3; install it now.

## Setup

```bash
cp .env.example .env     # local settings; .env is git-ignored
uv sync                  # create .venv from uv.lock (needs uv; uv run also does this)
make hooks                # install the commit-stage checks (see Quality gates)
make up                  # start Postgres and wait until it is healthy
make psql                # open psql inside the container; try: select 1;
```

`.env.example` holds a local-only placeholder password, not a real secret. Change values in `.env`, never in tracked files.

## Make targets

| Target | What it does |
| --- | --- |
| `make help` | List the targets |
| `make up` | Start the database and wait until it is healthy |
| `make down` | Stop the database; data is kept |
| `make reset` | Delete all database data and start clean |
| `make psql` | Open `psql` inside the database container |
| `make sample` | Generate the synthetic sample data |
| `make test` | Run the test suite |
| `make raw-table` | Create `raw.spotify_streams` from `sql/raw_spotify_streams.sql` |
| `make load` | Load `sample_data/` into the raw table (`SOURCE=data` for the real export) |
| `make inspect SOURCE=data` | Show the structure of an export folder, never its values |
| `make hooks` | Install the commit-stage checks (a git pre-commit hook) |
| `make lint` | Run every file check over all tracked files |
| `make scan` | Scan the commits of a range for secrets and IP addresses (`BASE=`, `HEAD=`) |
| `make pr-check` | Run everything the CI workflow runs, on a throwaway database |

The database listens on `127.0.0.1:5432` only (change `POSTGRES_PORT` in `.env` if the port is taken). Connection settings: user `owner`, database `spotify_mesh`, password from `.env`.

dbt v2 loads the Postgres adapter only with `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true`. The Make targets and `bin/dbt` set it, so run dbt as `bin/dbt <args>` (a wrapper around `uv run dbt`) and you never export it by hand. See [ADR 0001](docs/0001-dbt-v2-experimental-postgres.md).

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

## Roles and permissions

```bash
make roles                     # create the layers staging, marts, semantic, the roles dbt and agent, and the grants
make psql-agent                # connect as the agent: SELECT ip_addr is refused
make lint-contract             # validate the data contract in contracts/
```

Set `DBT_PASSWORD` and `AGENT_PASSWORD` in `.env` first (see `.env.example`). The agent role has no grant on `raw` or `staging`, so the restriction holds for every query, whatever the prompt says. See [sql/README.md](sql/README.md) and [contracts/README.md](contracts/README.md).

## Data handling

This repository is public, so what goes into git matters.

| Committed | Never committed |
| --- | --- |
| Code, SQL and dbt models | The real Spotify export (`data/`, except `data/README.md`) |
| Data contracts and eval questions | `.env` (your local settings) |
| Synthetic sample data in `sample_data/` | `.venv/` and local tool settings |

**Why the real export stays out of git:** it contains your IP address and a detailed record of what you listened to and when. Anything pushed to a public repository can be copied, cached and indexed, and deleting it later does not undo that. Synthetic data has the same shape and no personal content, so the pipeline, the tests and the demos use it instead.

Three layers keep personal data out, see [Quality gates](#quality-gates): a commit that stages a forbidden path, a secret or an IP address is refused; every pull request is checked again in CI; and `make test` checks that `data/` is ignored and that no tracked file contains an IPv4 or IPv6 address outside the reserved documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `2001:db8::/32`). The one-time audit of the whole git history is in [specs/004-quality-gates/history-audit.md](specs/004-quality-gates/history-audit.md); the hygiene test reads the working tree only.

## Quality gates

Automatic checks run before every commit and again on every pull request, so the rules of this repository do not depend on remembering them. They protect the one thing that cannot be undone in a public repository: personal data and secrets reaching git.

**One-time install:**

```bash
uv sync                # includes pre-commit
make hooks             # installs the git pre-commit hook
```

For `make scan` and `make pr-check`, also install [gitleaks](https://github.com/gitleaks/gitleaks/releases) v8.30.1: download `gitleaks_8.30.1_linux_x64.tar.gz` and the release's checksum file, check it with `sha256sum -c --ignore-missing`, and put the `gitleaks` binary on your `PATH` (for example `~/.local/bin`). The CI workflow pins the same version and checksum.

**What runs before each commit** (staged files only, a docs-only commit takes well under a second):

| Check | Refuses |
| --- | --- |
| `path-guard` | A staged file from `data/` (except its guide), `.env`, `.env.ci`, `.claude/settings.local.json` or a key file, even when added with `git add -f` |
| `gitleaks` | A secret or an IPv4 address outside the reserved ranges; the message gives file and line and never prints the value |
| `check-merge-conflict`, `check-added-large-files` | Conflict markers; files over 500 KB |
| `ruff-check`, `ruff-format` | Python lint errors; unformatted Python (the formatter rewrites the file, stage it and commit again) |
| `sqlfluff-lint` | SQL lint errors in `sql/` |
| `yamllint` | YAML errors in contracts, `docker-compose.yml` and the workflow |
| `contract-lint` | An invalid data contract (Data Contract CLI) |

The commit stage does not run the test suite and does not need the database.

**The three commands:**

| Command | Does | Needs |
| --- | --- | --- |
| `make lint` | The file checks above over all tracked files | `uv` |
| `make scan [BASE= HEAD=]` | Secrets and IP addresses in the commits of a range (default `origin/main..HEAD`) | `gitleaks` |
| `make pr-check [BASE= HEAD=]` | Everything the CI workflow runs: `lint`, `scan`, then a throwaway database from the sample data and the full test suite | Docker, `gitleaks`, `uv` |

`make pr-check` uses its own database (compose project `smesh-ci`, port 55432, generated credentials in `.env.ci`) and removes it afterwards. It never touches your own database or its data.

**In CI:** `.github/workflows/ci.yml` has one job, `checks`, on every pull request and on every push to `main`. It installs the tools and runs `make pr-check`; it lists no check itself, so the local commands and CI cannot drift apart. It uses a read-only token and no secret, and a skipped database test counts as a failure. `git commit --no-verify` skips the local stage, and CI catches the same problem.

**Allowing a reviewed false positive:** one narrow entry, with a reason written next to it, in the file of the check that complained:

| Check | File |
| --- | --- |
| Secret and IP scan | `.gitleaks.toml` (`[[allowlists]]` or the allowlist of the rule) |
| Python lint | `pyproject.toml` (`[tool.ruff.lint.per-file-ignores]`) |
| SQL lint | `.sqlfluff` (rule list), or `.sqlfluffignore` for one file as a last resort |
| YAML lint | `.yamllint.yaml` (`ignore:`) |
| Path guard | none: a file that must be tracked belongs outside the guarded paths |

**Recommended branch protection** (a repository setting; enabling it is the owner's decision): a ruleset on `main` that requires a pull request, requires the status check `checks` (after the workflow has run once, so GitHub lists it), blocks force pushes and blocks deletion.

## Next phase

Phase 3 builds the dbt staging layer and `fct_listens`. See [.claude/plans/implementation-plan.md](.claude/plans/implementation-plan.md).

## Troubleshooting

| Situation | Symptom | Fix |
| --- | --- | --- |
| Docker not reachable from WSL | `docker: command not found`, mentioning WSL integration | Enable WSL integration for your distro in Docker Desktop settings |
| Port already in use | Compose error when binding the port | Set `POSTGRES_PORT` in `.env` to a free port |
| Password unset | `required variable POSTGRES_PASSWORD is missing a value` | `cp .env.example .env` |
| Stale database state | Old tables are still there | `make reset` |
| uv missing | `uv: command not found` | Install [uv](https://docs.astral.sh/uv/) |
| dbt rejects Postgres | `The 'postgres' adapter is not yet supported by dbt` | Set `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true` (the Make targets already do) |
| dbt cannot connect | `libpq.so.5: cannot open shared object file` | `sudo apt install libpq5` |
| `error: uv is required` or `error: run uv sync first` | A quality-gate target cannot find the tool | Install [uv](https://docs.astral.sh/uv/), then `uv sync` |
| `error: gitleaks is required` | `make scan` or `make pr-check` cannot find the scanner | Install gitleaks v8.30.1 (see Quality gates) |
| A commit is refused | The hook names the check, the file and the line | Fix it, or add one reasoned allowance (see Quality gates) |
| `dbt --version` shows `1.x` | An older dbt is in the same environment | `rm -rf .venv && uv sync`; keep only `dbt-oss` in `pyproject.toml` |
