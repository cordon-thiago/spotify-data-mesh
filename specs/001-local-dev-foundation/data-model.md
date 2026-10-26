# Data Model: Local Development Foundation

Entities from the spec. Field names and shapes come from the owner's real samples (23 fields). Nothing here is loaded into a database in Phase 0; ingestion starts in Phase 1.

## Stream record

One playback event. Every record carries all 23 keys, in this order; unused ones are `null`.

| # | Field | Type | Nullable | Notes |
| --- | --- | --- | --- | --- |
| 1 | `ts` | string, ISO 8601 UTC (`2025-12-31T12:18:21Z`) | no | Instant the stream **ended** |
| 2 | `platform` | string | no | e.g. `android`, `ios`, `windows` |
| 3 | `ms_played` | integer | no | Milliseconds played, > 0 |
| 4 | `conn_country` | string, 2 letters | no | e.g. `PT` |
| 5 | `ip_addr` | string, IPv4 | no | **Restricted.** Synthetic: RFC 5737 range only |
| 6 | `master_metadata_track_name` | string | yes | Music only |
| 7 | `master_metadata_album_artist_name` | string | yes | Music only |
| 8 | `master_metadata_album_album_name` | string | yes | Music only |
| 9 | `spotify_track_uri` | string `spotify:track:<22 base-62>` | yes | Music only |
| 10 | `episode_name` | string | yes | Podcast only |
| 11 | `episode_show_name` | string | yes | Podcast only |
| 12 | `spotify_episode_uri` | string `spotify:episode:<22 base-62>` | yes | Podcast only |
| 13 | `audiobook_title` | string | yes | Audiobook only |
| 14 | `audiobook_uri` | string `spotify:show:<22 base-62>` | yes | Audiobook only |
| 15 | `audiobook_chapter_uri` | string `spotify:episode:<22 base-62>` | yes | Audiobook only |
| 16 | `audiobook_chapter_title` | string | yes | Audiobook only |
| 17 | `reason_start` | string | no | e.g. `trackdone`, `clickrow`, `fwdbtn`, `appload`, `unknown` |
| 18 | `reason_end` | string | no | e.g. `trackdone`, `endplay`, `fwdbtn`, `logout`, `unexpected-exit-while-paused` |
| 19 | `shuffle` | boolean | yes | `null` allowed |
| 20 | `skipped` | boolean | yes | `null` allowed |
| 21 | `offline` | boolean | yes | `null` allowed |
| 22 | `offline_timestamp` | integer, epoch seconds | yes | Not derived from `ts` |
| 23 | `incognito_mode` | boolean | yes | `true` = private session |

The audiobook URI shapes (`spotify:show:`, chapter as `spotify:episode:`) are assumptions: the owner's samples show these fields only as `null`. They are confirmed against the real export in Phase 1.

**Content type** is implied by which descriptor group is filled; exactly one group is non-null per record:

| Content | Filled fields | File |
| --- | --- | --- |
| Music | 6 to 9 | audio |
| Audiobook | 13 to 16 | audio |
| Podcast episode | 10 to 12 | video |

### Validation rules (enforced by the generator tests)

- All 23 keys present, in the order above.
- Exactly one descriptor group non-null.
- `ms_played` is a positive integer; `ts` parses as UTC and falls in 2024-01-01 to 2025-12-31.
- `ip_addr` is inside `192.0.2.0/24`, `198.51.100.0/24` or `203.0.113.0/24`.
- URIs match their `spotify:<kind>:<22 base-62>` pattern.

## Sample dataset

A deterministic set of stream records written as two JSON array files.

| Attribute | Rule |
| --- | --- |
| Identity | `(seed, records)` pair; defaults `42` and `2000` |
| Size | `records` total across both files, 100 to 10,000,000 |
| Mix (random body) | about 80% music, 15% podcast, 5% audiobook |
| Null booleans | about 5% `null` in each of `shuffle`, `skipped`, `offline`, `incognito_mode` |
| Private sessions | about 3% `incognito_mode = true` |
| Injected edge cases | fixed block present at any size (see below) |
| Determinism | same `(seed, records)` gives byte-identical files |

### Injected edge cases (always present)

| Category | Minimum count | Purpose in later phases |
| --- | --- | --- |
| `null` in each of the four booleans | 2 per field | Null handling in rates |
| `incognito_mode = true` | 3 | Private-session policy |
| Crosses local midnight in `Europe/Lisbon` (winter, UTC offset 0) | 2 | Local-time conversion |
| Crosses local midnight in `Europe/Lisbon` (summer, UTC+1) | 2 | DST-aware conversion |
| Exact duplicate of another record | 3 | Deduplication |
| Audiobook stream | 3 | Third content type |
| Podcast and music with same artist/show string shape | 1 | Artist vs show distinction |

## Local environment

Described entirely by tracked files; no persistent entity beyond the database volume.

| Part | Source of truth | State that persists |
| --- | --- | --- |
| Database service `db` | `docker-compose.yml`, `.env` | Named volume `pgdata` |
| Python toolchain | `requirements*.txt`, `.venv/` | `.venv/` (ignored) |
| Sample data | `sample_data/generate.py` and its two output files | Tracked files |

### Relationships

- A **Sample dataset** contains many **Stream records** and is produced by the generator.
- The **Local environment** consumes no data in Phase 0; Phase 1 links the dataset to the database.
