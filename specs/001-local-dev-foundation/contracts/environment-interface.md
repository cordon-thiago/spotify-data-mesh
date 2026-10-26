# Contract: local environment interface

What a person, and later phases, can rely on. Satisfies FR-003 to FR-006.

## Database service

| Item | Value |
| --- | --- |
| Compose service name | `db` |
| Image | `postgres:16` |
| Host binding | `127.0.0.1:${POSTGRES_PORT}` (default `5432`) |
| Container port | `5432` |
| Database | `${POSTGRES_DB}` (default `spotify_mesh`) |
| User | `${POSTGRES_USER}` (default `owner`) |
| Password | `${POSTGRES_PASSWORD}`, required; startup fails with a clear message if unset |
| Volume | named `pgdata`, mounted at `/var/lib/postgresql/data` |
| Healthcheck | `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}`; healthy within 60 s |
| Restart | `unless-stopped` is not used; the service runs only when started |

Phase 2 adds the `dbt` and `agent` roles and the `raw`, `staging`, `marts` and `semantic` schemas through `sql/roles.sql`. This phase creates none of them.

## Environment file

`.env.example` (tracked) lists the four variables with local-only placeholder values. `.env` (ignored) is created with `cp .env.example .env`. The password placeholder is not a real secret and must not be reused anywhere else.

## Make targets

| Target | Does | Underlying command |
| --- | --- | --- |
| `make up` | Start the database and wait until healthy | `docker compose up -d --wait` |
| `make down` | Stop the database; data kept | `docker compose down` |
| `make reset` | Stop and delete data, then start clean | `docker compose down -v` then `up -d --wait` |
| `make psql` | Open `psql` inside the container | `docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB` |
| `make venv` | Create `.venv` and install pinned requirements | `python3.12 -m venv .venv` and `pip install -r requirements-dev.txt` |
| `make sample` | Generate sample data | `.venv/bin/python sample_data/generate.py` |
| `make test` | Run the test suite | `.venv/bin/pytest` |

## Python environment

- `.venv/` at the repository root, Python 3.12.
- `requirements.txt`: `dbt-oss==2.0.8` (dbt v2). Do not add `dbt` or `dbt-core` to the same environment: they share the `dbt` entry point.
- `requirements-dev.txt`: `-r requirements.txt` and `pytest==9.1.1`.
- The Makefile exports `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true`; anyone running `.venv/bin/dbt` by hand must set it before using the Postgres adapter (README documents this).
- System library `libpq5` is required for dbt to connect to Postgres (`sudo apt install libpq5`); needed from Phase 3, listed as a prerequisite now.
- Check: `.venv/bin/dbt --version` prints a version starting with `2.`.

## Failure behaviour (README documents each)

| Situation | Visible symptom | Documented fix |
| --- | --- | --- |
| Docker not reachable from WSL | `docker: command not found` mentioning WSL integration | Enable WSL integration in Docker Desktop |
| Port already in use | Compose error on bind | Set `POSTGRES_PORT` in `.env` |
| Password unset | Compose error `POSTGRES_PASSWORD is required` | `cp .env.example .env` |
| Stale database state | Old tables present | `make reset` |
| Wrong Python version | `make venv` stops with a version message | Install Python 3.12 |
| dbt rejects Postgres | `The 'postgres' adapter is not yet supported by dbt` | Set `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true` (Make targets already do) |
| dbt cannot connect | `libpq.so.5: cannot open shared object file` | `sudo apt install libpq5` |
| `dbt --version` shows `1.x` | Old dbt in the same environment | Recreate `.venv`; keep only `dbt-oss` |
