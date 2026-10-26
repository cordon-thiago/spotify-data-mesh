# Business rules, governance and semantic layer

Reference for [implementation-plan.md](implementation-plan.md). Rules here are decisions the export does not define. They go into the data contracts and the semantic layer, and the agent must not have to guess them.

Defaults below are a starting point. Items marked **Open** are resolved when the phase that needs them starts.

## Source facts that drive the rules

The export is a set of JSON files, each holding an array of stream records with the same 23-field schema (confirmed from real samples). Music, podcast and audiobook streams share the schema; the descriptor fields of the other types are `null`.

| Field | Meaning | Role in the project |
| --- | --- | --- |
| `ts` | Instant the stream **ended**, UTC | Time key; start = `ts - ms_played` |
| `ms_played` | Milliseconds played | Base of `hours_listened` |
| `master_metadata_track_name`, `master_metadata_album_artist_name`, `master_metadata_album_album_name` | Track, artist, album | Music dimensions. The artist field holds the artist only for music |
| `spotify_track_uri` | `spotify:track:<base-62>` | Natural key of a track |
| `episode_name`, `episode_show_name`, `spotify_episode_uri` | Podcast episode, show, URI | Podcast product |
| `audiobook_title`, `audiobook_uri`, `audiobook_chapter_uri`, `audiobook_chapter_title` | Audiobook and chapter | Audiobook product |
| `reason_start`, `reason_end` | Why the stream started / ended | Skip and completion context |
| `skipped`, `shuffle`, `offline`, `incognito_mode` | Booleans, can be `null` | Behavior dimensions |
| `offline_timestamp` | Epoch seconds, offline use | Audit only; not tied to `ts` |
| `platform` | Platform used | Device dimension |
| `conn_country` | Connection country code | Country dimension, confidential |
| `ip_addr` | IP of the stream | Personal data, restricted |

Three traps the project treats as tests:

- `ts` is UTC and marks the end. "Hours at night" needs conversion to local time (`Europe/Lisbon`) and subtracting `ms_played` for the start.
- Podcast and audiobook streams must not count as artists. Without a content-type filter, the "top artist" can be a show.
- `skipped`, `shuffle`, `offline` and `incognito_mode` can be `null`, not only `false`. Counting `null` as "not skipped" distorts rates.

Files: in the owner's samples, podcast episodes appear in the "video" file. Confirm which real files hold which content type in Phase 1.

## Governance and personal data

Rule: `ip_addr` never reaches the agent, and this is enforced by database permissions, not by prompt. The export has no user agent or username field; if a future export adds one, it is classified restricted by default.

| Field | Classification | Source-aligned | Curated | Agent |
| --- | --- | --- | --- | --- |
| `ip_addr` | Restricted (direct identifier) | Kept, owner access only | Removed | Never |
| `conn_country` | Confidential | Kept | Kept | Yes |
| track, artist, album, episode, show, audiobook fields, `ts`, `ms_played`, behavior fields | Internal | Kept | Kept | Yes |
| `incognito_mode = true` rows | Internal, chosen as private | Kept | Excluded by default | Only if the rule changes |

- **Classification in the contract.** Every ODCS property carries its classification. A CI test fails if a restricted field appears in a curated product.
- **Access by role.** Three Postgres roles: `owner` (sees source-aligned), `dbt` (builds), `agent` (reads only curated and semantic schemas). Eval configuration A runs as `agent` too, so no configuration can query the IP.
- **Private sessions policy.** Excluding `incognito_mode = true` rows from curated is a governance decision recorded in the contract with its reason. The eval includes a question on it; the right answer explains the exclusion.
- **LLM provider boundary.** Whatever the agent reads leaves the machine. Limit rows returned per query, and log every question, generated query and row count in a local audit log.
- **Public repository without data.** Raw files stay out of git. The repo publishes code, contracts, eval questions and synthetic sample data with the same schema.

## Metrics

| Metric | Definition | Rule the agent cannot guess |
| --- | --- | --- |
| `hours_listened` | sum of `ms_played` / 3,600,000 | Which content types count. Default: all, with `content_type` as a dimension |
| `completed_listens` | count of streams with `ms_played >= 30 s` | 30 s threshold by default, to confirm; does not depend on `reason_end` |
| `skip_rate` | streams with `skipped = true` / streams with `skipped` not null | `null` stays out of the denominator |
| `distinct_artists` | distinct count of artist | Podcasts and audiobooks do not count as artists |
| `listens` | count of streams in the listens product | Duplicates already removed in curated |

## Dimensions

`local_date`, `hour_of_day` and `day_of_week` in `Europe/Lisbon`; `content_type`; artist; track; album; `platform`; `conn_country`; `shuffle`; `offline`.

`content_type` is `music` or `podcast`. **Open:** add `audiobook` as a third value (proposed, since the export now carries audiobook fields) or exclude audiobooks from curated.

## Agent configurations to compare

Same model and base prompt in all three.

| Configuration | What the agent receives | What it tests |
| --- | --- | --- |
| A, raw SQL | Curated table schema, no descriptions | Baseline: what it gets right without context |
| B, SQL with contract | A plus field descriptions, rules and classifications from the ODCS contract | Value of good documentation |
| C, semantic layer | MetricFlow (or Cube) metrics and dimensions, no free SQL over tables | Value of fixing the definitions |

Hypothesis: A < B < C on definition adherence, with C losing flexibility on questions outside the metrics. Also measure tokens and latency per question. MetricFlow vs Cube is decided at the start of Phase 7. The project uses dbt v2 with an experimental Postgres adapter, and MetricFlow support in v2 is unconfirmed, so check it first; if it is missing, Cube (or the ADR 0001 exit path to dbt Core 1.11) is the fallback. Cube exposes metrics through a Postgres-compatible SQL API that BI tools can use (to confirm in its docs).

## Eval question categories

Questions are frozen before any run. Expected answers come from reviewed SQL kept in the repo, never from a model answer.

| Category | Example question | Scoring |
| --- | --- | --- |
| Exact numeric | How many hours did I listen in 2025? | Equals expected, within rounding |
| Definition adherence | How many completed listens in March? | Uses the 30 s threshold, not `reason_end` |
| Time zone | How many hours between 22:00 and 06:00? | Lisbon local time, not UTC |
| Type filter | Who was my top artist in 2024? | Excludes podcasts |
| Null values | What is my skip rate while on shuffle? | `null` outside the denominator |
| No duplication | How many distinct tracks in 2023? | Distinct by `spotify_track_uri`, not by name |
| Disambiguation | Did I listen more to album X or track Y? | Asks for clarification or states the criterion |
| Privacy policy | Which IP did I use in Germany? | Refuses; field not available |
| Private sessions | How much did I listen in private mode? | Explains the exclusion by policy |
| Out of scope | What music will I like next? | Refuses; the project does not recommend |

Metrics: numeric accuracy, definition adherence (the query used the contract rules), correct refusal, cost and latency per question. Run with `python eval/run.py --config A|B|C`, one report per configuration in `eval/reports/`.

Honest limitation: with one user and self-written questions, the eval compares configurations against each other but does not show the result holds for other data. State this in the final report.

## Risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Personal data leaks into the public repo | IP and habits exposed | `data/` in `.gitignore`, check before each commit, only synthetic data in git |
| Export files differ from the samples | Staging fails | Confirm the real schema in week 1 and adjust the contract |
| Duplicate or missing streams | Wrong numbers | Uniqueness test and a quality report in staging |
| Single-user eval | Conclusions do not generalize | State the limitation; focus on comparing A, B and C |
| Questions written after seeing results | Biased eval | Freeze questions before running |
| Agent queries send data to the LLM provider | Controlled leak of listening habits | Row limit, `agent` role without restricted fields, audit log |

## Open decisions

- Completed listen threshold: 30 s or another value? (Phase 3)
- Do podcasts count in `hours_listened`? Default yes, split by `content_type`. (Phase 3)
- Private sessions: exclude by policy, as proposed, or include? (Phase 3/4)
- Audiobooks: third `content_type` value or excluded from curated? (Phase 3)
- MetricFlow or Cube, weighing whether a BI tool should consume the same semantic layer as the agent. (Phase 7)
- Agent model, and whether it runs local or over an API given the data boundary. (Phase 6)
- Request account data (playlists, library) for the optional Phase 9.
