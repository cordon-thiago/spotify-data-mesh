# Research: Local Development Foundation

All Technical Context unknowns are resolved below. No `NEEDS CLARIFICATION` remains.

## 1. PostgreSQL version and image

- **Decision**: `postgres:16` (Debian-based official image), pinned to the major version.
- **Rationale**: Mature, a standard target for dbt's Postgres adapters, and supported upstream until late 2028. The Debian image includes `psql` and `pg_isready`, which the healthcheck and `make psql` use.
- **Alternatives**: `postgres:17` (newer, no feature needed in this project); `postgres:16-alpine` (smaller, but locale and extension surprises are not worth the saved megabytes for a learning project).

## 2. Database access without a host `psql`

- **Decision**: `make psql` runs `docker compose exec db psql` inside the container. A host `psql` client is optional and works against the published port.
- **Rationale**: `psql` is not installed in the current WSL distro, and the container always has a matching client. The spec's checkpoint ("psql connect") is satisfied either way.
- **Alternatives**: Require a host `psql` (extra install step, version drift); use a Python driver for the check (not a `psql` check, hides Docker/Postgres basics the learner wants to see).

## 3. Docker availability

- **Decision**: Document Docker Desktop with WSL integration as a prerequisite and have the README show the exact symptom and fix.
- **Rationale**: A first probe found `docker` missing in the WSL distro; the owner then confirmed Docker Desktop with WSL integration, and a second probe showed Docker 27.3.1 and Compose v2.30.3 working. Installing a separate Docker engine inside WSL would diverge from the owner's Docker Desktop setup.
- **Alternatives**: Install Docker Engine in WSL (conflicts with Desktop integration, out of scope); run Postgres natively with apt (loses the Docker learning goal and reproducibility).

## 4. Credentials and configuration

- **Decision**: `.env.example` is tracked with placeholder local-only values; `.env` is created by copying it and is git-ignored. `docker-compose.yml` reads `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` and `POSTGRES_PORT` from the environment, and fails fast if the password is unset (`${POSTGRES_PASSWORD:?...}`). Defaults: user `owner`, database `spotify_mesh`, host port `5432` bound to `127.0.0.1` only.
- **Rationale**: Satisfies FR-004 (configurable without editing tracked files, no real secret). The `owner` user name matches the constitution's role model, so Phase 2 extends it rather than renaming it. Binding to loopback keeps the database off the network.
- **Alternatives**: Hard-coded credentials in compose (violates FR-004); Docker secrets (overkill for a local dev database).

## 5. Persistence and reset

- **Decision**: One named volume `pgdata`. `make down` stops the service and keeps data; `make reset` runs `docker compose down -v` and starts clean.
- **Rationale**: Meets FR-005 with two obvious commands and no manual file deletion.
- **Alternatives**: Bind-mounting a host folder (permission problems on WSL, easy to commit by accident).

## 6. Python environment and pins

- **Decision**: Python 3.12 venv at `.venv`, created by `make venv`. `requirements.txt` pins `dbt-oss==2.0.8` (dbt v2, the open-source Apache 2.0 runtime); `requirements-dev.txt` pins `pytest==9.1.1`. The venv must not also contain `dbt` or `dbt-core`: they share the `dbt` entry point. The Makefile exports `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true` for dbt targets.
- **Rationale**: The owner chose dbt v2. Probed on this machine: `dbt-oss` 2.0.8 installs and reports `2.0.8`; its supported adapters are Snowflake, BigQuery, Databricks, Redshift, DuckDB, Salesforce and ClickHouse; Postgres parses only with the experimental flag, and a connection needs `libpq.so.5`. There is no `dbt-postgres` package in v2; adapters are bundled. Python 3.12 is already installed.
- **Alternatives**: dbt Core 1.11 with `dbt-postgres` (stable, MetricFlow-ready; rejected by the owner for now); DuckDB with v2 (supported adapter, but no roles or grants, which breaks constitution principle I); `uv tool install dbt-oss` (works, but a venv keeps dbt, pytest and the generator in one place); Poetry or `pyproject.toml` (more machinery than two requirement files need); ruff/black (YAGNI in Phase 0).
- **Risks accepted**: experimental Postgres adapter may be unstable; v2 is a Rust runtime with a tightly defined project language, so macros and config follow v2 rules; MetricFlow support is unconfirmed (Phase 7 may need Cube); the Python programmatic interface for dbt v2 is not available yet. Recorded in ADR 0001, with the exit path: move to dbt Core 1.11 + `dbt-postgres` if the experimental adapter blocks a phase.

## 7. Generator design

- **Decision**: A single standard-library script, `sample_data/generate.py`, using `random.Random(seed)`. Records are produced lazily and written one at a time as a JSON array, so memory stays flat. Time window is fixed (2024-01-01 to 2025-12-31 UTC) so output does not depend on the run date. Defaults: 2,000 records, seed 42.
- **Rationale**: Meets FR-007 to FR-010. No third-party dependency means no version drift in the fixture. A fixed window and seeded RNG give byte-identical output (FR-008).
- **Alternatives**: Faker (extra dependency and locale data drift; real-looking names are unnecessary); pandas (heavy, not streaming).
- **Determinism caveat**: `random.Random` output is stable for a given seed within a Python minor version; the guarantee is tested by running twice, not by a golden hash.

## 8. Edge-case coverage

- **Decision**: After the random body, the generator injects a fixed block of edge-case records: `null` in each optional boolean, private sessions (`incognito_mode: true`), streams that cross local midnight (`Europe/Lisbon`, summer and winter), exact duplicates for dedup tests, audiobook streams, and episodes. The minimum accepted size is 100 records so every category always fits; the maximum is 10,000,000.
- **Rationale**: FR-010 and SC-004 require every category regardless of size. Injecting by construction beats hoping the RNG produces them.
- **Alternatives**: Rely on probability (flaky at small sizes); a separate edge-case file (later phases would need to combine two inputs).

## 9. File layout and names

- **Decision**: Two committed files, `streaming_history_audio_sample.json` (music and audiobook streams) and `streaming_history_video_sample.json` (podcast episodes), each a JSON array with Spotify's `"key" : value` spacing. Real file names are confirmed in Phase 1.
- **Rationale**: Mirrors the owner's samples, where episodes appear in the "video" example. Keeping two files tests that ingestion handles several files with one schema.
- **Alternatives**: One combined file (hides the audio/video split); invent real-looking names such as `Streaming_History_Audio_2024_0.json` (implies knowledge we do not have yet).

## 10. Synthetic and restricted values

- **Decision**: IPs come from the RFC 5737 documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`). Track, artist, album, show, episode and audiobook names are synthetic ("Synthetic Track 0042"). Spotify URIs use the correct shape with random base-62 IDs.
- **Rationale**: FR-011. Reserved ranges cannot identify a real device, and the hygiene test can recognise them. Synthetic names avoid any resemblance to the owner's listening history.
- **Alternatives**: `Faker` IPs (may collide with real ones); copy real titles from the owner's samples (leaks taste, violates the public-repo spirit).

## 11. Git policy for `data/`

- **Decision**: `.gitignore` uses `data/*` and `!data/README.md`, plus `.env`, `.venv/`, `__pycache__/` and `.pytest_cache/`. The earlier plain `data/` line is replaced.
- **Rationale**: FR-012 and the constitution's principle V. A tracked README keeps the folder present after a clone and explains why it is empty; every other file placed there stays ignored.
- **Alternatives**: Ignore the whole folder (it would not exist after clone); `.gitkeep` (explains nothing).

## 12. Command surface

- **Decision**: A Makefile with `up`, `down`, `reset`, `psql`, `venv`, `sample`, `test`, each also documented as the raw command in the README.
- **Rationale**: One discoverable surface keeps the README short and the learner can read each target to see the underlying command.
- **Alternatives**: Shell scripts (more files); `just` or Task (extra install).

## 13. Repository hygiene test

- **Decision**: `tests/test_repo_hygiene.py` (a) runs `git check-ignore` on a dummy path under `data/`, and (b) scans files from `git ls-files` for IPv4 addresses and fails on any outside the reserved documentation ranges, loopback and the `00.000.000.000` mask.
- **Rationale**: Turns SC-005 and the learning checkpoint into an automated check. It cannot prove history is clean, so the README tells the owner to run the same scan before each push.
- **Alternatives**: A pre-commit hook (extra tooling this early); trust-based review (not repeatable).
