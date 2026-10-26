# Quickstart: validate Raw Ingestion

Runnable checks that prove the feature end to end. Interfaces: [contracts/ingest-cli.md](contracts/ingest-cli.md) and [contracts/raw-table-conventions.md](contracts/raw-table-conventions.md). Entities: [data-model.md](data-model.md).

## Prerequisites

- Phase 0 working: `make venv`, `make up`, `make sample` done; `make test` passes.
- `make venv` re-run once so `psycopg` from `requirements.txt` is installed.
- For sections 4 and 5 only: the real export ZIP extracted into a subfolder of `data/` (for example `data/export/`).

## 1. Write and apply the table definition (the owner's exercise ✍️)

Edit `sql/raw_spotify_streams.sql`: create schema `raw` and table `raw.spotify_streams` with one column per JSON field (same names as the keys) plus `source_file`. Choose the types yourself. Then:

```bash
make raw-table
make psql        # \d raw.spotify_streams
```

Expected: the table exists. Before this step, `make load` must refuse to run (section 2, first check).

## 2. Load the sample data (User Story 1)

```bash
make load                      # before the table exists: stops with the "write sql/raw_spotify_streams.sql" message
make raw-table && make load
```

Expected: the report shows, for each file and in total, `read` equal to `loaded`, and the `NULL` counts of `shuffle`, `skipped`, `offline` and `incognito_mode` equal on both sides; result `committed`. Exit code 0.

Cross-check by hand:

```bash
make psql        # select source_file, count(*) from raw.spotify_streams group by 1;
```

Expected: counts equal the report (1688 and 312 for the default sample).

Null preservation:

```bash
make psql        # select count(*) filter (where shuffle is null), count(*) filter (where incognito_mode is null) from raw.spotify_streams;
```

Expected: same figures as the report.

Re-run:

```bash
make load && make psql   # select count(*) from raw.spotify_streams;   -- still 2000
```

Expected: 2000 rows, not 4000. Duplicates in the sample stay in the table.

## 3. Failure behaviour (all-or-nothing)

```bash
mkdir -p /tmp/bad_export && cp sample_data/streaming_history_audio_sample.json /tmp/bad_export/ \
  && echo '[{"ts": "x"}' > /tmp/bad_export/streaming_history_broken.json
make load SOURCE=/tmp/bad_export
make psql        # select count(*) from raw.spotify_streams;   -- still 2000
```

Expected: exit code 2, a message naming `streaming_history_broken.json` and a position, no field values printed, and the table unchanged.

Value-free errors: rename a column in a throwaway copy of the table, or load into a column typed too strictly; the error must show the file, the line and the column but never the value.

## 4. Inspect the real export (User Story 2)

```bash
make inspect SOURCE=data/export
```

Expected: per file, record counts, key counts, JSON types, null counts, keys outside the 23-field schema, content-type groups, and the list of ignored files. No values are printed.

Write the findings into `docs/real-export-findings.md` (structure and counts only). Update `sql/raw_spotify_streams.sql`, the loader's file rule and the generator if the real schema differs. Then `make test` (the IPv4 scan covers the new document).

## 5. Load the real export (User Story 3)

```bash
make load SOURCE=data/export
```

Expected: per-file and total counts equal, `NULL` counts equal, result `committed`; the output shows file names and counts only. Then:

```bash
git status --short       # nothing from data/ and no new file with real values
make test
```

## 6. Automated checks

```bash
make test
```

Expected: unit tests pass without Docker; with the database up, the integration tests also pass (they use a throwaway schema, not `raw.spotify_streams`).

## Checkpoint (from the implementation plan)

JSON record count equals table row count, per file and in total, and `null` booleans are preserved and counted. Sections 2 and 6 prove it for the sample data; sections 4 and 5 prove it for the real export once the ZIP is available.
