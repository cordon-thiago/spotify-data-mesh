# ADR 0001: Use dbt v2 with the experimental Postgres adapter

- **Status**: Accepted
- **Date**: 2026-10-25
- **Deciders**: Project owner

## Context

The project was planned on dbt Core 1.x with `dbt-postgres`. The owner wants dbt v2 (the open-source Rust runtime, package `dbt-oss`, Apache 2.0).

Probed on 2026-10-25 with `dbt-oss` 2.0.8:

- Supported adapters: Snowflake, BigQuery, Databricks, Redshift, DuckDB, Salesforce, ClickHouse.
- Postgres is not supported. `dbt parse` fails with `The 'postgres' adapter is not yet supported by dbt` unless `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true` is set. With the flag, `dbt parse` succeeds.
- Connecting to Postgres needs the system library `libpq.so.5`; without it `dbt debug` fails.
- There is no `dbt-postgres` package for v2: adapters are bundled.
- `dbt` and `dbt-core` share the `dbt` entry point with `dbt-oss`, so they cannot live in the same environment.
- v2 documentation describes the release as early (alpha announced June 2026); sources disagree on whether it is general availability. MetricFlow support in v2 is not documented.

## Decision

Use `dbt-oss` (dbt v2) with the experimental Postgres adapter, enabled through `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true` in the Makefile targets and documented in the README. Keep Postgres as the database because the privacy model (principle I) relies on database roles and grants.

## Alternatives considered

| Option | Why not chosen |
| --- | --- |
| dbt Core 1.11 with `dbt-postgres` | Stable and MetricFlow-ready, but the owner prefers v2. Kept as the exit path. |
| dbt v2 with DuckDB | Supported adapter, but DuckDB has no roles or grants, so principle I (privacy by permission) would need a MAJOR amendment. |

## Consequences

- The adapter may be unstable; a bug in it can block a phase.
- MetricFlow may not work with v2. Phase 7 checks this first and falls back to Cube, or to the exit path.
- `libpq5` becomes a system prerequisite (`sudo apt install libpq5`).
- v2 follows a stricter project language; projects written for v1 may need `dbt-autofix`.
- No programmatic Python interface for invoking v2 yet; the project calls the CLI.

## Exit path

If the experimental adapter blocks a phase, switch to dbt Core 1.11 with `dbt-postgres` (before v2 usage grows): replace `dbt-oss` in `requirements.txt`, drop the experimental flag, and run `dbt parse` to confirm. Revisit when Postgres reaches supported status in v2.

## Review trigger

Re-evaluate at the start of Phase 3 (first real dbt project) and Phase 7 (semantic layer).
