# Spotify Data Mesh Constitution

## Core Principles

### I. Privacy by Permission, Not by Prompt (NON-NEGOTIABLE)
`ip_addr` and any user agent or username field the export may contain MUST NOT reach any
curated product, the semantic layer, the agent or the eval. This MUST be enforced by database roles and grants
(`owner`, `dbt`, `agent`), never by prompt instructions. The only door from the restricted
schema to the marts is `int_streams_deduplicated`. Every agent configuration (A, B, C) MUST run
as the `agent` role. Every agent query MUST be row-limited and written to a local audit log
(question, generated query, row count).
Rationale: the agent's reads leave the machine for the LLM provider, and prompts are not a
security boundary.

### II. Contracts as Code
Every data product (`spotify_streams`, `listens`, `listened_catalog`) MUST have an ODCS
contract in `contracts/`, validated by the Data Contract CLI. Every contract property MUST carry
a classification (restricted, confidential, internal). A CI test MUST fail if any restricted
field appears in a mart. Business rules the source does not define (completed listen threshold,
content-type split, incognito policy, local timezone) MUST be written in the contract and the
semantic layer, with a justification.
Rationale: the project's hypothesis is that explicit definitions make the agent err less.

### III. Layered, Tested Transformations
dbt models MUST follow `staging` → `intermediate` → `marts`, named `stg_<source>__<entity>`,
`fct_` and `dim_`, with one `_<folder>__models.yml` per folder. Staging is views; marts are
tables. `ts` is the UTC end of the stream; start time MUST be derived as `ts - ms_played`.
Nullable booleans (`skipped`, `shuffle`, `offline`, `incognito_mode`) MUST stay nullable and
`null` MUST be excluded from rate denominators. Podcasts MUST NOT count as artists. Each model
MUST have schema tests; rules with logic (timezone conversion, deduplication) MUST have a unit
or singular test.
Rationale: these are the known traps in the export, and each one is a tested rule, not a habit.

### IV. Frozen, Reproducible Eval
Eval questions MUST be frozen in `eval/questions.yaml` before any configuration runs against
them. Expected answers MUST come from reviewed SQL stored in `eval/expected/`, never from model
output. `python eval/run.py --config A|B|C` MUST reproduce every report in `eval/reports/`.
Reports MUST state the single-user limitation.
Rationale: writing questions after seeing results biases the comparison of A, B and C.

### V. Reproducible Without Personal Data
Raw export files MUST stay out of git (`data/` in `.gitignore`). The repository MUST publish
only code, contracts, eval questions and a synthetic `sample_data/` with the same 23-field
schema. The full pipeline MUST run end to end on `sample_data/` alone. Secrets and credentials
MUST NOT be committed, including anything under `.claude/` that holds them.
Rationale: the export contains IP addresses and listening habits that must never be published.

### VI. Learning-First Phased Delivery
Work MUST proceed in phases, each with one new concept, one running deliverable and one
checkpoint; a phase MUST NOT start until the previous checkpoint passes. Parts marked ✍️ in the
plan are written by the learner and MUST NOT be pre-filled by the assistant. Complexity beyond
the current phase MUST be justified in the plan.
Rationale: the project exists to learn data mesh practice; speed is secondary to understanding.

## Technology and Repository Constraints

- Stack: Postgres (local, Docker), dbt v2 (open-source `dbt-oss`; its Postgres adapter is
  experimental, see `docs/0001-dbt-v2-experimental-postgres.md`), ODCS contracts with the Data
  Contract CLI, Python for ingestion, agent and eval. The semantic layer is MetricFlow or Cube,
  decided at the start of Phase 7.
- Everything in the repository MUST be in English: identifiers, files, branches, commits,
  comments, YAML descriptions, eval questions, reports and ADRs.
- Naming: `content_type` (`music`/`podcast`), `hours_listened`, `skip_rate`, `distinct_artists`,
  `local_date`, `hour_of_day`, `day_of_week`, `is_completed_listen`.
- Out of scope: recommendations, other users' data and any call to the Spotify Web API.
- Local day and hour dimensions MUST use `Europe/Lisbon`.

## Development Workflow and Quality Gates

- A change is done only when `dbt build` passes and contract and privacy tests pass.
- Before each commit, verify that no file from `data/` or restricted field values are staged.
- Significant decisions (semantic layer tool, LLM local vs API, incognito policy, completed
  listen threshold) MUST be recorded as an ADR in `docs/`.
- Features follow the Spec Kit flow: specify → plan → tasks → implement, checked against this
  constitution at the plan step.

## Governance

This constitution supersedes other practices for this repository. Amendments MUST be made by
editing this file with a Sync Impact Report, a version bump and a documented reason. Versioning
follows semantic versioning: MAJOR for removing or redefining a principle, MINOR for adding a
principle or materially expanding guidance, PATCH for wording clarifications. Principle I
changes MUST NOT weaken the privacy guarantee without a MAJOR bump and an ADR. Every plan and
review MUST verify compliance; deviations MUST be justified in the plan's complexity tracking.
Runtime guidance lives in `.claude/plans/implementation-plan.md`.

**Version**: 1.0.2 | **Ratified**: 2026-10-25 | **Last Amended**: 2026-10-25
