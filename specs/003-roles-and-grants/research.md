# Research: Roles and Base Governance

Each item: decision, why, alternatives.

## R1. Access model: by layer, with default privileges

- **Decision**: `agent` gets no `USAGE` on `raw` and `staging`; `USAGE` on `marts` and `semantic` plus `SELECT` on their tables. `ALTER DEFAULT PRIVILEGES FOR ROLE dbt IN SCHEMA marts, semantic GRANT SELECT ON TABLES TO agent`. For raw: `ALTER DEFAULT PRIVILEGES FOR ROLE owner IN SCHEMA raw GRANT SELECT ON TABLES TO dbt`.
- **Why**: Without `USAGE` on a schema, every read inside it fails with `permission denied for schema`, even for columns added later. Column-level grants would need updating with each new column. Default privileges also cover views and tables recreated by dbt (`create or replace`, or build-then-rename), because they apply to every newly created object of that creator. For raw, they make `DROP TABLE` / `CREATE TABLE` in `raw_spotify_streams.sql` keep `dbt`'s read access, which satisfies FR-020 with no rerun.
- **Alternatives**: column-level `GRANT SELECT (cols)` to `agent` on raw (fragile, and the agent should not touch raw at all); re-grant after every dbt run through a hook (extra moving part, can be forgotten); row-level security (not needed, out of scope).

## R2. Who owns what

- **Decision**: `owner` (the existing Postgres user, a superuser in the Docker image) owns the four schemas and the raw table. `dbt` gets `USAGE` and `CREATE` on `staging`, `marts`, `semantic`, and `USAGE` on `raw`. `dbt` owns the objects it creates.
- **Why**: dbt must create and replace its own objects, and in PostgreSQL only an object's owner can drop or replace it. The consequence is that the object owner can also grant on it; PostgreSQL has no setting to forbid that. So FR-007 is stated as: `dbt` cannot grant on raw or on the layers, and the agent's access to dbt-built objects is guarded by the Phase 4 privacy test. A view in `marts` also runs with its owner's (`dbt`) rights, so a mart view over raw would expose `ip_addr` to the agent; this is the exact case Phase 4 tests.
- **Alternatives**: `dbt` owns the schemas (worse: it could then grant on them); `owner` creates every object on dbt's behalf (breaks dbt); event triggers that revert grants (too much machinery for a learning phase).

## R3. What `PUBLIC` holds in PostgreSQL 16

- **Decision**: `REVOKE ALL ON DATABASE spotify_mesh FROM PUBLIC` (removes `CONNECT` and `TEMP`) then grant `CONNECT` to `dbt` and `agent`, and `TEMP` to `dbt` only. `REVOKE ALL ON SCHEMA public FROM PUBLIC`. New schemas grant nothing to `PUBLIC` by default, so none needed there.
- **Why**: By default `PUBLIC` can connect and create temporary tables, and in 16 can use (not create in) schema `public`. The agent creating temp tables would break "read-only" (FR-005). `owner` is a superuser and is unaffected.
- **Alternatives**: leave defaults (violates FR-005, FR-009).

## R4. Passwords and idempotent role creation

- **Decision**: `.env` gets `DBT_PASSWORD` and `AGENT_PASSWORD`. `make roles` runs `psql -v dbt_password=... -v agent_password=... -f` through `docker compose exec -T`. In the script: `SELECT 'CREATE ROLE dbt LOGIN' WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dbt') \gexec`, then `ALTER ROLE dbt LOGIN PASSWORD :'dbt_password' NOSUPERUSER NOCREATEDB NOCREATEROLE`.
- **Why**: `CREATE ROLE IF NOT EXISTS` does not exist; `\gexec` is the idiomatic psql pattern. `:'var'` quotes the value safely. `ALTER ROLE` every run lets the owner rotate a password by rerunning. The values appear in the process list inside the local container only; acceptable for a loopback-only database and stated in the quickstart. Make fails with a clear message when a variable is missing.
- **Alternatives**: a `DO` block with `format()` (works but mixes SQL and PL/pgSQL for no gain); `PGPASSWORD` plus `\password` (interactive, not repeatable); hard-coded dev passwords (violates FR-011).

## R5. Tests connect as the real roles

- **Decision**: `tests/test_roles_db.py` opens one `psycopg` connection per role using passwords from `.env`/environment and asserts `psycopg.errors.InsufficientPrivilege` (SQLSTATE 42501) for each forbidden action. The owner creates a throwaway raw table `raw.t_<uuid>` with an `ip_addr` column, and the tests drop it. If the real `raw.spotify_streams` exists, extra read-only checks run against it.
- **Why**: The proof is the error the database returns, not a reading of the catalog. A throwaway table avoids dropping the owner's loaded real data (the raw table script drops it, so tests must not call it). The throwaway table also exercises the raw default privileges. Error text is never printed, since it can echo values; tests compare error classes.
- **Alternatives**: `has_table_privilege()` checks (kept as a cheap extra, but not the proof); applying `raw_spotify_streams.sql` in tests (destroys real data).

## R6. Data Contract CLI and ODCS

- **Decision**: `uv add --dev datacontract-cli`; target the ODCS v3 format (`apiVersion` value fixed when the file is written, checked by `datacontract lint`). Per property: `name`, `logicalType`, `physicalType`, `description`, `classification`, `required`/nullability as in the table, and `criticalDataElement` where useful. Access in the top-level `roles` section; the restricted reason and the "future fields are restricted" rule in `customProperties`/`description`. `make lint-contract` runs the lint.
- **Why**: Checked: the installed standard model has `classification`, `physicalType`, `roles` and `customProperties`. The lock resolves with dbt-oss (dry run, lock restored afterward).
- **Alternatives**: run the CLI by Docker image (extra tool for a Python project); a custom YAML schema (violates Principle II).
- **Open until tasks**: exact `apiVersion` string accepted by the lint; confirm by running it.

## R7. Contract-versus-table drift check

- **Decision**: In the DB test, read `information_schema.columns` for the raw table (a throwaway copy built from `raw_spotify_streams.sql` is not needed: the test reads `raw.spotify_streams` when it exists, else skips) and compare to the contract's properties: same names (set equality, with the failing field named), and `physicalType` equal to `information_schema.columns.data_type` text (`timestamp with time zone`, `inet`, `integer`, `bigint`, `boolean`, `text`).
- **Why**: Writing `physicalType` in PostgreSQL's own spelling makes the comparison direct. The CI database always has the table (setup applies it first).
- **Alternatives**: `datacontract test` against the live table (needs a server section with credentials in the contract, and runs more than needed); parsing the SQL file (brittle).

## R8. Catalog visibility

- **Decision**: Accept it. The agent can see names (including `ip_addr`) in `pg_catalog`; it cannot read values. `information_schema` already hides columns the role has no privileges on.
- **Why**: Hiding catalog names is not possible in a normal PostgreSQL role setup and gives no protection of values. Recorded in the spec's Assumptions so nobody mistakes it for a leak.

## R9. `make reset` and setup order

- **Decision**: Order for a clean machine: `make reset`, `make raw-table`, `make roles`, `make load`. `roles.sql` creates `raw` if it is missing, so it also works before the raw table exists; default privileges cover a table created later. `make roles` is safe to run before or after `make raw-table`.
- **Why**: Matches FR-010 and the edge case "setup before the table exists".
