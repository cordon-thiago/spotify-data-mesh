# Implementation plan: Spotify Data Mesh (phased, learning-first)

Source design: [.claude/plans/project-1-spotify.md](project-1-spotify.md).

## Goal

A personal data mesh over the Spotify extended streaming history export: Postgres + dbt Core + ODCS data contracts + semantic layer + AI agent + eval comparing three agent configurations (A, B, C).

Hypothesis: data contracts and a semantic layer make the agent err less than raw SQL over tables.

## Working principle

Each phase = **one new concept + one running deliverable + one learning checkpoint**. Steps are small and explained. Parts marked ✍️ are written by the learner before moving on. No phase starts until the previous checkpoint passes.

## Conventions

- Everything in the repository is in **English**: column, table, metric and dimension names, folders, files, branches, commits, comments, docstrings, contract and dbt YAML descriptions, eval questions and reports, ADRs, README.
- Raw export stays out of git (`data/` in `.gitignore`). Only code, contracts, eval questions and synthetic sample data are committed.
- Naming used in the design doc, translated:

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
- Folder structure from the design doc; `git init`; `.gitignore` with `data/`; English README.
- `docker-compose.yml` with Postgres; Python venv; `dbt-postgres`.
- `sample_data/`: synthetic generator with the 21 export fields (also the pipeline test fixture).
- Learn: why raw data stays out of git; Docker/Postgres basics.
- Checkpoint: `docker compose up` and `psql` connect; sample data generated.

### Phase 1: Raw ingestion (concept: source-aligned data, ELT)
- Inspect the real ZIP (file names and schema); adjust contract if it differs from the README.
- `ingest/load.py`: flatten JSON → CSV → `COPY` into restricted `raw.spotify_streams`.
- ✍️ Write the DDL column list and types.
- Checkpoint: JSON row count equals table row count; check `null` in boolean fields.

### Phase 2: Roles and base governance (concept: privacy by permission, not by prompt)
- Postgres roles `owner`, `dbt`, `agent`; schemas `raw`, `staging`, `marts`, `semantic`; GRANTs in `sql/roles.sql`.
- ODCS contract `contracts/spotify_streams.odcs.yaml` with per-field classification (IP, user agent, username = restricted).
- Checkpoint: as `agent`, `SELECT ip_addr_decrypted` fails.

### Phase 3: dbt staging + `fct_listens` (concept: dbt layers, tests, business rules)
- `dbt init`, sources, `stg_spotify__streams.sql` (rename, cast, `ts` is UTC end time → start = end − `ms_played`).
- `int_streams_deduplicated.sql`: drops IP / user agent / username (the only door from restricted to marts), dedups, excludes incognito.
- `fct_listens.sql`: `local_date`, `hour_of_day` in `Europe/Lisbon`, `content_type`, `is_completed_listen`.
- Tests: uniqueness, accepted values, nullable booleans, `ts` range, one singular test, one unit test on timezone conversion.
- ✍️ Write the dedup rule and the 30 s threshold.
- Checkpoint: `dbt build` green; manual "hours between 22:00 and 06:00" matches hand calculation.

### Phase 4: Catalog + privacy CI (concept: multiple data products, contracts as code)
- `dim_listened_catalog` keyed by `spotify_track_uri`; contracts for `listens` and `listened_catalog`.
- Data Contract CLI test; a test that **fails if any restricted field appears in marts**.
- Checkpoint: deliberately add `ip_addr_decrypted` to a mart and watch the test fail.

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

About one session per phase (design doc assumes ~4 h/week). Per phase: concept explained → small implementation steps → learner's ✍️ part → checkpoint → next phase.
