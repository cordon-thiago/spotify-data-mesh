# Data Model: Roles and Base Governance

## Layers (schemas)

| Layer | Purpose | Created by | Owner | `dbt` | `agent` |
| --- | --- | --- | --- | --- | --- |
| `raw` | Source-aligned, restricted (holds `ip_addr`) | Phase 0/1 (`roles.sql` creates it if missing) | `owner` | `USAGE`; `SELECT` on tables (default privilege) | none |
| `staging` | One-to-one cleaned views of the source | `roles.sql`, filled by dbt | `owner` | `USAGE`, `CREATE`; owns its objects | none |
| `marts` | Curated data products | `roles.sql`, filled by dbt | `owner` | `USAGE`, `CREATE`; owns its objects | `USAGE`; `SELECT` on `dbt`-built tables and views (default privilege) |
| `semantic` | Governed metric objects for the agent | `roles.sql`, filled by dbt (Phase 7) | `owner` | `USAGE`, `CREATE`; owns its objects | `USAGE`; `SELECT` on `dbt`-built tables and views (default privilege) |

`public` schema: `PUBLIC` loses all access. dbt `intermediate` models are built as views in `staging`; no extra schema.

## Roles

| Role | Login | Can create roles | Database privileges | Purpose |
| --- | --- | --- | --- | --- |
| `owner` | yes (exists; superuser in the Docker image) | yes | all | Owns layers and the raw table; runs setup, loader and the raw table script |
| `dbt` | yes, password from `DBT_PASSWORD` | no | `CONNECT`, `TEMP` | Builds `staging`, `marts`, `semantic`; reads `raw` |
| `agent` | yes, password from `AGENT_PASSWORD` | no | `CONNECT` only (no `TEMP`) | Reads curated data; connection created in Phase 6 |

None of `dbt` and `agent` is superuser, can create databases or roles, or is a member of another role.

## Data contract (`contracts/spotify_streams.odcs.yaml`)

| Element | Content |
| --- | --- |
| Identity | name `spotify_streams`, version `1.0.0`, status `active`, domain `listening` |
| Description | Source-aligned Spotify streaming history, one row per export record, unchanged. Restricted layer. |
| `roles` | `owner` (read, write), `dbt` (read); `agent`: no access, stated in the description |
| Schema object | `raw.spotify_streams`, 25 properties |
| Property | `name`, `logicalType`, `physicalType` (PostgreSQL spelling), `description`, `classification`, nullability |

### Classification of the 25 properties

| Classification | Properties |
| --- | --- |
| `restricted` | `ip_addr` (direct identifier; owner and `dbt` only; never in a mart, the semantic layer or the agent) |
| `confidential` | `conn_country` |
| `internal` | `ts`, `platform`, `ms_played`, the three music fields, `spotify_track_uri`, `episode_name`, `episode_show_name`, `spotify_episode_uri`, the four audiobook fields, `reason_start`, `reason_end`, `shuffle`, `skipped`, `offline`, `offline_timestamp`, `incognito_mode`, `source_file`, `loaded_at` |

Rules: every property has exactly one classification; exactly one is restricted; the four nullable booleans state that `null` means unknown; the contract states that a user agent or username field added by a future export is restricted by default.

### Validation rules

- Lint passes (FR-016).
- Property names equal the table's column names, and `physicalType` equals the table's `data_type` (FR-017).
- Classification values are limited to `restricted`, `confidential`, `internal`.

## Credentials

| Setting | In `.env` | In `.env.example` |
| --- | --- | --- |
| `DBT_PASSWORD` | real local value | `change_me_local_only` placeholder |
| `AGENT_PASSWORD` | real local value | `change_me_local_only` placeholder |
