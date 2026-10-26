# Real export findings

What the real Spotify extended streaming history export looks like, found by running `make inspect SOURCE=data` and a structure-only check on 2026-10-26. This document holds **structure and counts only**: no track, artist, episode or show names, no IP addresses, no dates of listening. Specification: [specs/002-raw-ingestion/](../specs/002-raw-ingestion/).

## Files

The export was extracted directly into `data/` (no subfolder, no ZIP kept).

| File name pattern | Files | Records | Content found |
| --- | --- | --- | --- |
| `Streaming_History_Audio_<year>.json` | 11 | 6,801 | 5,977 music, 824 podcast episodes, 0 audiobook |
| `Streaming_History_Video_<year>.json` | 5 | 1,121 | 1,064 podcast episodes, 57 music, 0 audiobook |
| **Total** | **16** | **7,922** | 6,034 music, 1,888 podcast episodes, 0 audiobook |

Every record fills exactly one content group (music, podcast or audiobook); none fills zero or several. File names carry a year, not a part number (`_<year>`, not `_0`).

## Excluded

Nothing from the export is excluded: all 16 files match the loader's default rule `streaming_history_*.json` (case-insensitive). The only other file in `data/` is our own `README.md`, which the loader lists as ignored. The export had no read-me or account-data files in this extraction.

## Schema

Same as the sample schema.

- All **23 keys** are present in every record of every file. No key outside the 23, none absent.
- JSON types per key:

| Keys | JSON types |
| --- | --- |
| `ts`, `platform`, `conn_country`, `ip_addr`, `reason_start`, `reason_end` | string, never null |
| `ms_played` | number, never null |
| track fields (4), episode fields (3) | string or null, depending on the content type of the record |
| `audiobook_*` (4) | always null in this export |
| `shuffle`, `skipped`, `incognito_mode` | boolean, never null |
| `offline` | boolean or null (262 nulls, all in `Video` files) |
| `offline_timestamp` | number or null (2,284 nulls) |

## Facts that bear on the table definition

- **`ts`**: always a UTC time in the form `YYYY-MM-DDTHH:MM:SSZ`.
- **`ms_played`**: always an integer, never negative, at most 7 digits.
- **`offline_timestamp`**: always an integer when present, but **two units are mixed**: 5,633 values have 10 digits (seconds) and 5 have 13 digits (milliseconds). Interpreting the unit belongs to Phase 3.
- **`ip_addr`**: **IPv4 (7,748) and IPv6 (174)** both occur. The Phase 0 generator and the repository IP scan only knew IPv4.
- **`conn_country`**: always two uppercase letters.
- **URIs**: every `spotify_track_uri` (6,034) and `spotify_episode_uri` (1,888) has the shape `spotify:<track|episode>:<22 base-62 characters>`.
- **Text lengths**: longest `platform` is 54 characters, track name 159, album 117, artist 31, episode name 191, show name 73, `reason_start` 10, `reason_end` 28. There are 17 distinct `platform` values, 9 of `reason_start` and 12 of `reason_end`.
- **Empty strings are not nulls**: `episode_show_name` is an empty string in 4 records. Raw data must keep them apart (FR-003, FR-004).
- **Null booleans**: only `offline` (262). `shuffle`, `skipped` and `incognito_mode` have none, but the load still compares all four.
- **Exact duplicates**: 12 extra copies of records exist in the export. They are loaded as they are; removing them is Phase 3.
- **Private sessions**: no record has `incognito_mode = true`.

## Content type does not follow the file name

This contradicts an earlier assumption (episodes in the "video" file only):

- `Audio` files from the second half of the history contain podcast episodes as well as music.
- One `Video` file contains music records (57) next to podcast episodes.

The content type of a record must be derived from which fields are filled, never from the file name (Phase 3).

## Size

6.05 MB in total; the largest file is 1.26 MB and the largest holds 1,669 records. Reading one file at a time with `json.load` is safe. A full load is expected to take seconds, far below the 10-minute budget (SC-004).

## Decisions

1. **File rule**: keep `streaming_history_*.json`, recursive, case-insensitive. No change.
2. **Schema**: no field to add or remove. The table needs the 23 columns plus `source_file`.
3. **Generator** (`sample_data/generate.py`), updated to match the real export:
   - place records in both files regardless of content type, as the real export does;
   - emit some IPv6 addresses from the documentation range `2001:db8::/32`;
   - include records whose `episode_show_name` is an empty string, next to `null`.
4. **Repository IP scan** (`tests/test_repo_hygiene.py`): also catch IPv6 addresses outside `2001:db8::/32`.
5. **Table definition**: the owner's (✍️). The facts above are the inputs; this document does not choose types.
6. **Load time and counts**: recorded after the real load, below.

## Real load result

Loaded on 2026-10-26 with `make load SOURCE=data` into `raw.spotify_streams` (the table in `sql/raw_spotify_streams.sql`).

| Check | Result |
| --- | --- |
| Records read = rows loaded | 7,922 = 7,922, and equal for each of the 16 files |
| `NULL` counts, file side = table side | `shuffle` 0, `skipped` 0, `incognito_mode` 0, `offline` 262 |
| Second load | Same 7,922 rows (a load replaces the table content) |
| Load time | 0.36 s for the whole export |
| Table figures match this document | IPv4 7,748 and IPv6 174; empty `episode_show_name` 4 (and none turned into `NULL`); `offline_timestamp` null 2,284, 10 digits 5,633, 13 digits 5; music 6,034, podcast 1,888, audiobook 0; Audio files 6,801 rows, Video files 1,121 |
| Type fit | No value was rejected by the column types (`timestamptz`, `integer`, `inet`, `bigint`, `boolean`) |

The memory use stayed small: one file (the largest is 1.26 MB) is read at a time, so the per-file `json.load` is not a concern for an export of this size.
