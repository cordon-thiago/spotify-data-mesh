# Implementation plan: Spotify Data Mesh (phased, learning-first)

Business rules, governance, metrics and eval design: [business-rules.md](business-rules.md).

## Goal

A personal data mesh over the Spotify extended streaming history export: Postgres + dbt v2 + ODCS data contracts + semantic layer + AI agent + eval comparing three agent configurations (A, B, C).

Hypothesis: data contracts and a semantic layer make the agent err less than raw SQL over tables.

## Working principle

Each phase = **one new concept + one running deliverable + one learning checkpoint**. Steps are small and explained. Parts marked ✍️ are written by the learner before moving on. No phase starts until the previous checkpoint passes.

## Conventions

- Everything in the repository is in **English**: column, table, metric and dimension names, folders, files, branches, commits, comments, docstrings, contract and dbt YAML descriptions, eval questions and reports, ADRs, README.
- Raw export stays out of git (`data/` in `.gitignore`). Only code, contracts, eval questions and synthetic sample data are committed.
- Folder structure (dbt conventions: `staging` / `intermediate` / `marts`, `stg_<source>__<entity>`, `fct_` and `dim_`, one `_<folder>__models.yml` and `_<source>__sources.yml` per folder, staging as views, marts as tables):

```text
spotify-data-mesh/
  data/                                  # raw export, kept out of git
  sample_data/                           # synthetic, same schema, committed
  ingest/                                # JSON → CSV → COPY loader
  sql/                                   # roles.sql, DDL
  contracts/                             # one ODCS contract per data product
    spotify_streams.odcs.yaml
    listens.odcs.yaml
    listened_catalog.odcs.yaml
  dbt/
    dbt_project.yml
    packages.yml
    models/
      staging/spotify/
        _spotify__sources.yml
        _spotify__models.yml
        stg_spotify__streams.sql
      intermediate/
        _int_listens__models.yml
        int_streams_deduplicated.sql
      marts/listens/
        _listens__models.yml
        _listens__semantic_models.yml
        fct_listens.sql
      marts/catalog/
        _catalog__models.yml
        dim_listened_catalog.sql
    tests/  macros/
  agent/                                 # configurations A, B and C
  eval/
    questions.yaml
    expected/
    run.py
    reports/
  docs/                                  # ADRs
```

- Naming used in the original design, translated:

| Design doc | Project |
| --- | --- |
| `tipo_conteudo` | `content_type` (`music` / `podcast`) |
| `horas_ouvidas` | `hours_listened` |
| `taxa_de_salto` | `skip_rate` |
| `artistas_distintos` | `distinct_artists` |
| `data_local`, `hora_do_dia`, `dia_da_semana` | `local_date`, `hour_of_day`, `day_of_week` |
| audição completa | `completed_listen` (`is_completed_listen`) |

## Defaults for open decisions

Resolved when the phase that needs them starts.

- Completed listen = `ms_played >= 30s` (Phase 3).
- Podcasts count in `hours_listened`, split by `content_type` (Phase 3).
- `incognito_mode = true` rows excluded from curated by policy (Phase 3/4).
- LLM local vs API (Phase 6). MetricFlow vs Cube (Phase 7; MetricFlow recommended first).

## Phases

### Phase 0: Foundation (concept: reproducible environment)
- Folder structure from the Conventions section; `git init`; `.gitignore` with `data/`; English README.
- `docker-compose.yml` with Postgres; Python venv; `dbt-oss` (dbt v2, Postgres adapter experimental, see `docs/0001-dbt-v2-experimental-postgres.md`).
- `sample_data/`: synthetic generator with the 23 export fields (also the pipeline test fixture).
- Learn: why raw data stays out of git; Docker/Postgres basics.
- Checkpoint: `docker compose up` and `psql` connect; sample data generated. **Done 2026-10-26** (spec in `specs/001-local-dev-foundation/`): `make up` healthy in 6.7 s, data survives a restart, `make reset` cleans it, `make sample` writes 2000 records in 0.13 s with identical output on rerun, 35 tests pass.

### Phase 1: Raw ingestion (concept: source-aligned data, ELT)
- Inspect the real ZIP (file names and schema); adjust contract if it differs from the README. Real samples show 23 fields (adds four `audiobook_*` fields; `ip_addr`; no `user_agent_decrypted` or `username`) and podcast episodes in the "video" file; confirm which files hold which content types.
- `ingest/load.py`: flatten JSON → CSV → `COPY` into restricted `raw.spotify_streams`.
- ✍️ Write the DDL column list and types.
- Checkpoint: JSON row count equals table row count; check `null` in boolean fields. **Done 2026-10-26** (spec in `specs/002-raw-ingestion/`): 7,922 real records = 7,922 rows, per file and in total; `NULL` booleans equal on both sides (`offline` 262); reload leaves the same rows; loads in 0.4 s. Findings: `docs/real-export-findings.md`.

### Phase 2: Roles and base governance (concept: privacy by permission, not by prompt)
- Postgres roles `owner`, `dbt`, `agent`; schemas `raw`, `staging`, `marts`, `semantic`; GRANTs in `sql/roles.sql`.
- ODCS contract `contracts/spotify_streams.odcs.yaml` with per-field classification (`ip_addr` = restricted; the real export has no user agent or username field).
- Checkpoint: as `agent`, `SELECT ip_addr` fails. **Done 2026-11-15** (spec in `specs/003-roles-and-grants/`): as `agent`, `SELECT ip_addr`, `SELECT *` and any read of `raw` or `staging` fail with `permission denied for schema`; `dbt` reads raw (7,922 rows) and cannot delete from or drop it; the contract lists 25 properties (1 restricted, 1 confidential, 23 internal), lints clean and matches the table. Limits found: `dbt` owns what it builds and can grant on it (the Phase 4 privacy test is the guard), and `agent` can see object names, not values, in the catalog.

### Phase 2b: Quality gates (concept: automated checks before and after commit)
- Pre-commit (`.pre-commit-config.yaml`): path guard (no `data/`, no local settings, no key files, even with `git add -f`), gitleaks on staged changes (secrets and IPv4 addresses outside the reserved ranges), ruff (lint + format) for Python, sqlfluff for `sql/`, yamllint for contracts, compose and the workflow, and `datacontract lint` on `contracts/*.odcs.yaml`.
- CI (`.github/workflows/ci.yml`): one job `checks` on every PR and push to `main`; it installs the tools and runs `make pr-check`: the file checks over the whole repository, a gitleaks scan of the commits of the PR, then a throwaway Postgres (compose project `smesh-ci`) on `sample_data/` with `sql/` applied and the full test suite. Never touches the real export or the owner's database.
- `make` targets: `hooks` (install), `lint` (file checks), `scan` (secrets and IPs over a commit range) and `pr-check` (everything the workflow runs), so local and CI behave the same. Tool choices: [ADR 0002](../../docs/0002-quality-gates-tooling.md).
- Out of scope: the "restricted field in marts" test (Phase 4) and dbt checks (Phase 3 adds `dbt build` to CI once it exists).
- Checkpoint: a commit with a bad contract or a staged `.env` is blocked locally; a PR with a failing test shows a red check. **Implemented 2026-11-22** (spec in `specs/004-quality-gates/`): refused locally were a staged `data/` file, a fake token, a public IPv4 address, an invalid contract, an unused import, a long SQL line and a malformed YAML (no value printed); a documentation-range address passes. The history audit of 29 commits found 0 secrets and 0 real IP addresses ([history-audit.md](../../specs/004-quality-gates/history-audit.md)). A commit takes 0.4 s (docs) to 1.2 s (code and contract); `make pr-check` takes 20 s with 155 tests and leaves the owner's database untouched. The red-check part (a PR with a failing test) is verified on the first pull request.

### Phase 3: dbt staging + `fct_listens` (concept: dbt layers, tests, business rules)
- `dbt init`, sources, `stg_spotify__streams.sql` (rename, cast, `ts` is UTC end time → start = end − `ms_played`).
- `int_streams_deduplicated.sql`: drops `ip_addr` (the only door from restricted to marts), dedups, excludes incognito.
- `fct_listens.sql`: `local_date`, `hour_of_day` in `Europe/Lisbon`, `content_type`, `is_completed_listen`.
- Tests: uniqueness, accepted values, nullable booleans, `ts` range, one singular test, one unit test on timezone conversion.
- ✍️ Write the dedup rule and the 30 s threshold.
- Checkpoint: `dbt build` green; manual "hours between 22:00 and 06:00" matches hand calculation.

### Phase 4: Catalog + privacy CI (concept: multiple data products, contracts as code)
- `dim_listened_catalog` keyed by `spotify_track_uri`; contracts for `listens` and `listened_catalog`.
- Data Contract CLI test; a test that **fails if any restricted field appears in marts**.
- Checkpoint: deliberately add `ip_addr` to a mart and watch the test fail.

### Phase 5: Initial eval, config A (concept: measurable baseline)
- `eval/questions.yaml` with 12 questions, **frozen before any run**; expected answers from reviewed SQL in `eval/expected/`.
- `agent/` config A: raw schema only, role `agent`, row limit, local audit log.
- `python eval/run.py --config A` writes `eval/reports/`.
- ✍️ Write the questions and review the expected SQL.
- Checkpoint: report reproducible with one command; analyse where A fails (timezone, podcasts, nulls).

### Phase 6: Config B + larger eval (concept: value of documentation)
- Config B injects field descriptions, rules and classifications from the ODCS contracts.
- Grow eval from 12 to ~25 (privacy, incognito, out of scope, disambiguation).
- Checkpoint: A vs B delta per category.

### Phase 7: Semantic layer, config C (concept: governed metrics)
- Choose MetricFlow or Cube. Define `hours_listened`, `completed_listens`, `skip_rate`, `distinct_artists`, `listens` and the dimensions in `_listens__semantic_models.yml`.
- Config C uses metrics and dimensions only, no free SQL over tables.
- Checkpoint: same question gives the same answer via the metric query and via manual SQL.

### Phase 8: Final eval and report (concept: honest evaluation)
- 40+ frozen questions; run A, B, C; measure numeric accuracy, definition adherence, correct refusal, tokens, latency.
- Report states the single-user limitation. ADRs in `docs/`.
- Checkpoint: `python eval/run.py --config A|B|C` reproduces everything; hypothesis A < B < C confirmed or refuted.

### Phase 9 (optional): account data and article
- Second source-aligned product (playlists, library) joined by `spotify_track_uri`; agent audit; write-up.

## Critical files

- `docker-compose.yml`, `ingest/load.py`, `sql/roles.sql`
- `contracts/*.odcs.yaml`
- `dbt/models/{staging,intermediate,marts}/...`
- `agent/`, `eval/{questions.yaml,run.py,reports/}`

## Verification

- Phases 0–4: `docker compose up`, load sample data, `dbt build`, contract tests, `psql` as `agent` denied on restricted fields.
- Phases 5–8: `python eval/run.py --config A|B|C`, compare reports per category.
- Whole pipeline must run on `sample_data/` without the real export.

## Pace

About one session per phase (assumes ~4 h/week). Per phase: concept explained → small implementation steps → learner's ✍️ part → checkpoint → next phase.
