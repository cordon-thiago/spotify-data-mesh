# Quickstart: validate Roles and Base Governance

Runnable checks. Interfaces: [contracts/roles-and-grants.md](contracts/roles-and-grants.md), [contracts/spotify-streams-contract.md](contracts/spotify-streams-contract.md). Entities: [data-model.md](data-model.md).

## Prerequisites

- Phases 0 and 1 working: `uv sync`, `make up`, `make sample`.
- `.env` has `DBT_PASSWORD` and `AGENT_PASSWORD` (copy the new lines from `.env.example` and choose local values).
- `uv sync` re-run once so the Data Contract CLI is installed.

## 1. Clean setup (User Story 4)

```bash
make reset
make raw-table
make roles
make load
```

Expected: no errors. `make roles` prints the layers and roles it ensured, with no password.

## 2. The checkpoint: the agent cannot read the IP (User Story 1)

```bash
make psql-agent        # or: connect as agent
```

Then, as `agent`: `select ip_addr from raw.spotify_streams;`, `select * from raw.spotify_streams;`, `select 1 from staging.anything;`.

Expected: each fails with `permission denied`. As `owner` (`make psql`), `select count(ip_addr) from raw.spotify_streams;` returns a number.

## 3. The pipeline role (User Story 2)

As `dbt`: create a view in `staging` and a table in `marts` from `raw.spotify_streams`, read both. Then as `agent`: read the `marts` table (works) and the `staging` view (refused). As `dbt`: `delete from raw.spotify_streams;`, `drop table raw.spotify_streams;`, `grant select on raw.spotify_streams to agent;` all fail.

## 4. The contract (User Story 3)

```bash
make lint-contract
uv run pytest tests/test_contract.py
```

Expected: lint passes; the drift test passes. Rename one property in the YAML and rerun: the test fails and names the field.

## 5. Repeatable (User Story 4)

```bash
make roles && make roles
uv run pytest tests/test_roles_db.py
make raw-table                       # drops and recreates the raw table
uv run pytest tests/test_roles_db.py # still passes, without rerunning roles
```

Expected: no errors; the matrix in the contract holds.

## 6. Hygiene (SC-006)

```bash
make test
git grep -nE '(DBT|AGENT)_PASSWORD=.+' -- . ':!.env.example'
```

Expected: tests pass; the grep finds nothing.
