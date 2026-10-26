# Quickstart: validate the Local Development Foundation

Runnable checks that prove the feature works end to end. Interfaces are defined in [contracts/](contracts/) and the record shape in [data-model.md](data-model.md).

## Prerequisites

- Docker Desktop with WSL integration enabled (`docker compose version` prints a version).
- Python 3.12 and GNU Make.
- `libpq5` (`sudo apt install libpq5`), needed by dbt v2 to reach Postgres from Phase 3.
- A clean clone of the repository. No Spotify export is needed.

## 1. Configure and start the database (User Story 1)

```bash
cp .env.example .env
make up
make psql        # then run: select 1;
```

Expected: `make up` returns after the service reports healthy; `select 1;` returns one row; `\q` exits.

Restart check:

```bash
make down && make up
make psql        # same user, database and port work again
```

Reset check: `make reset` returns a clean database (no tables from earlier sessions).

## 2. Create the Python environment

```bash
make venv
.venv/bin/dbt --version
```

Expected: a version starting with `2.` (dbt v2, `dbt-oss` 2.0.8). The Postgres connection check (`dbt debug`) is done in Phase 3 and needs `libpq5` and `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true`.

## 3. Generate sample data (User Story 2)

```bash
make sample
sha256sum sample_data/*.json
make sample            # run twice
sha256sum sample_data/*.json
```

Expected: two files in `sample_data/`; both runs print identical checksums (identical output). Each file is a JSON array whose records have the 23 keys.

Different dataset:

```bash
make sample RECORDS=5000 SEED=7
```

Expected: different content, same schema. Restore the committed files afterwards with `make sample`.

Invalid input:

```bash
.venv/bin/python sample_data/generate.py --records 0
```

Expected: exit code 2 and `error: --records must be between 100 and 10000000`.

## 4. Data stays out of git (User Story 3)

```bash
echo '{}' > data/export_test.json
git status --short data/
rm data/export_test.json
```

Expected: nothing listed for `data/export_test.json`. The README's data-handling section explains why.

## 5. Automated checks

```bash
make test
```

Expected: all tests pass: generator schema, determinism, edge cases, input validation, `data/` ignored, and no non-reserved IPv4 address in any tracked file.

## Checkpoint (from the implementation plan)

`make up` and `make psql` connect, and `make sample` produces valid data. Together with `make test` passing, Phase 0 is done.
