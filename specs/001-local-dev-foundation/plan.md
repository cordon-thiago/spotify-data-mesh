# Implementation Plan: Local Development Foundation

**Branch**: `001-local-dev-foundation` (spec directory only; work stays on `main`) | **Date**: 2026-10-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-local-dev-foundation/spec.md`

## Summary

Phase 0 gives the project a reproducible local base: the repository folder skeleton with a short README per folder, a Postgres service started with one command, a pinned Python environment with dbt, and a deterministic generator of synthetic Spotify streaming-history files with the real 23-field schema. Nothing here touches the real export. The approach is deliberately small: Docker Compose for the database, a Makefile as the single command surface, a standard-library-only Python generator, and pytest tests that double as the checkpoint (database reachable, sample data valid, no personal data in git).

## Technical Context

**Language/Version**: Python 3.12 (venv in `.venv`), GNU Make, Docker Compose v2 file format

**Primary Dependencies**: `dbt-oss==2.0.8` (dbt v2, open-source Rust runtime installed from PyPI; installed, not yet used), `pytest==9.1.1` (dev). The generator uses only the Python standard library. The Postgres adapter is **experimental** in dbt v2 and needs `DBT_ALLOW_EXPERIMENTAL_ADAPTERS=true`; see [ADR 0001](../../docs/0001-dbt-v2-experimental-postgres.md).

**Storage**: PostgreSQL 16 in a container (`postgres:16`), data in a named volume. Sample data as JSON files in `sample_data/`.

**Testing**: pytest (`make test`): generator schema, determinism, edge cases, input validation, repository hygiene (no real IPs in tracked files, `data/` ignored).

**Target Platform**: Linux and WSL2 with Docker Desktop; macOS works with the same commands. Native Windows shells are out of scope.

**Project Type**: Data pipeline project (infrastructure and tooling; no service or UI in this phase)

**Performance Goals**: Database accepts a connection within 60 s of `make up` (SC-002); default dataset generated in under 30 s (SC-003); clean clone to working connection in under 15 min (SC-001).

**Constraints**: No real export is read or copied (FR-014). Output is byte-identical for the same seed and size on the same Python minor version. Generator memory stays bounded for large sizes (records are streamed to disk).

**Scale/Scope**: Default 2,000 records committed to git; configurable from 100 to 10,000,000 records. About 6 tracked files of code plus folder READMEs.

**Open environment findings**:

- Docker was initially missing from the WSL distro. Resolved on 2026-10-25: Docker Desktop WSL integration is enabled for `Ubuntu-22.04` (Docker 27.3.1, Compose v2.30.3, daemon reachable). `psql` is still not installed on the host; `make psql` uses the client inside the container. Docker Desktop with WSL integration stays a documented prerequisite.
- dbt v2 loads the Postgres adapter only with the experimental flag, and connecting needs the system library `libpq.so.5` (`sudo apt install libpq5`). Probed on this machine with `dbt-oss` 2.0.8: `dbt parse` succeeds with the flag and fails without it; `dbt debug` fails on the missing `libpq`. Phase 0 only checks `dbt --version`; the connection check belongs to Phase 3, but `libpq5` is listed as a prerequisite now.
- Measured on 2026-10-26 (WSL2, Docker Desktop): `make up` healthy in 6.7 s from a pulled image; `make sample` (2000 records) 0.13 s; 1,000,000 records in 27 s at 17 MB peak memory; `dbt-oss` 2.0.8 installed with the pinned requirements and no `dbt` or `dbt-core`.
- MetricFlow support in dbt v2 is unconfirmed. This affects the Phase 7 choice (MetricFlow vs Cube), not Phase 0.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Privacy by Permission | PASS | No real or restricted data in this phase. The only restricted field, `ip_addr`, is generated from reserved documentation ranges. Roles and grants arrive in Phase 2. |
| II. Contracts as Code | PASS (not applicable yet) | First ODCS contract is Phase 2. The `contracts/` folder is created with a README only. |
| III. Layered, Tested Transformations | PASS (not applicable yet) | `dbt/` is a README placeholder; `dbt init` is Phase 3. Installing dbt v2 is verified with `dbt --version` starting with `2.`. |
| IV. Frozen, Reproducible Eval | PASS (not applicable yet) | `eval/` folders only. |
| V. Reproducible Without Personal Data | PASS | `data/` ignored (README allowed); `sample_data/` synthetic and committed; hygiene test scans tracked files for non-reserved IPs; no secrets committed (`.env` ignored, `.env.example` tracked). |
| VI. Learning-First Phased Delivery | PASS | One concept (reproducible environment), one deliverable, one checkpoint; no ✍️ parts in Phase 0. |
| Technology constraints | PASS after amendment | Postgres, dbt (now v2 OSS), Python. The constitution named `dbt-postgres`, which does not exist for v2; amended to 1.0.2 with an ADR. |
| Quality gates | PASS | Gate for this phase is `make test` plus `dbt --version` and a `psql` connection; no dbt models exist yet. |

**Post-design re-check**: unchanged. The design adds no new dependency beyond the constitution's stack and introduces no violation.

## Project Structure

### Documentation (this feature)

```text
specs/001-local-dev-foundation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── generator-cli.md
│   └── environment-interface.md
├── checklists/requirements.md
└── tasks.md              # created by /speckit-tasks
```

### Source Code (repository root)

```text
.env.example                  # tracked template; real .env is ignored
.gitignore
Makefile                      # up, down, reset, psql, venv, sample, test
README.md                     # prerequisites, setup, data-handling policy
docker-compose.yml            # service "db" (postgres:16), named volume
requirements.txt              # pinned runtime dep (dbt-oss, dbt v2)
requirements-dev.txt          # pinned dev deps (pytest)
pytest.ini                    # pythonpath = sample_data
data/
└── README.md                 # only tracked file; everything else ignored
sample_data/
├── README.md
├── generate.py               # deterministic generator (stdlib only)
├── streaming_history_audio_sample.json
└── streaming_history_video_sample.json
tests/
├── test_generator.py
└── test_repo_hygiene.py
ingest/README.md              # Phase 1
sql/README.md                 # Phase 2
contracts/README.md           # Phase 2 and 4
dbt/README.md                 # Phase 3
agent/README.md               # Phases 5 to 7
eval/README.md                # Phases 5 to 8
docs/
├── README.md                 # ADR index
└── 0001-dbt-v2-experimental-postgres.md
```

**Structure Decision**: Single-repository, flat layout matching the Conventions tree in `.claude/plans/implementation-plan.md`. Empty phase folders hold a one-paragraph README so they exist in git and are "explained" (FR-001). The generator lives next to its output in `sample_data/` because it is the fixture's source of truth. Tests are at the repository root so later phases add to the same suite.

## Complexity Tracking

No constitution violations to justify.
