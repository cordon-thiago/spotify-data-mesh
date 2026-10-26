# Contract: ingest command line

Interfaces exposed by `ingest/load.py` and `ingest/inspect_export.py`, and the Make targets that wrap them. Satisfies FR-001, FR-006 to FR-014.

## Loader

```text
python ingest/load.py [--source DIR] [--pattern GLOB] [--table SCHEMA.TABLE]
```

| Option | Default | Rule |
| --- | --- | --- |
| `--source` | `sample_data` | Folder searched recursively for export files |
| `--pattern` | `streaming_history_*.json` | Case-insensitive file-name glob. Files that do not match are listed as ignored |
| `--table` | `raw.spotify_streams` | Target table. Tests use a throwaway table; normal use keeps the default |

Connection settings come from the environment, as set by `.env` through the Makefile: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT` (and optional `POSTGRES_HOST`, default `127.0.0.1`). A missing password stops the run with a clear message.

### Make targets

| Target | Does | Underlying command |
| --- | --- | --- |
| `make raw-table` | Apply the owner's table definition | `docker compose exec -T db psql -v ON_ERROR_STOP=1 -U $POSTGRES_USER -d $POSTGRES_DB < sql/raw_spotify_streams.sql` |
| `make load` | Load the sample data | `.venv/bin/python ingest/load.py --source $(or $(SOURCE),sample_data)` |
| `make load SOURCE=data/<folder>` | Load the real export from the private folder | same, with `SOURCE` |

### Behaviour

1. Check the target table (see [raw-table-conventions.md](raw-table-conventions.md)); stop before reading data if it is not usable.
2. Find the files; stop if none match.
3. In one transaction: empty the table, then load each file in sorted order, streaming rows.
4. Compare counts and commit only if every figure matches; otherwise roll back.

A run replaces the previous content of the table. Running the same input twice gives the same table.

### Report (stdout, on success and on mismatch)

Names, counts and nothing else:

```text
source: sample_data  table: raw.spotify_streams
file                                   read  loaded  null shuffle  null skipped  null offline  null incognito_mode
streaming_history_audio_sample.json    1688    1688             k             k             k                    k
streaming_history_video_sample.json     312     312             k             k             k                    k
TOTAL                                  2000    2000             k             k             k                    k
ignored: README.md
result: committed
```

`null ...` columns show the `NULL` count on the file side and the table side; they are printed as `file/table` when they differ. The report never contains field values.

### Exit codes

| Code | When | Message (stderr) |
| --- | --- | --- |
| `0` | Loaded and verified | The report above |
| `1` | Counts differ between source and table | The report with the differing figures, then `error: counts differ, load rolled back` |
| `2` | Bad input or configuration | One line naming the cause: no matching files; invalid JSON in `<file>` at line L, column C; `<file>` is not an array of records; unknown key `<key>` in `<file>`; missing key `<key>` in `<file>`; table `<table>` not found, write `sql/raw_spotify_streams.sql` and run `make raw-table`; column `source_file` missing |
| `3` | Database error | `error: database error in <file>: <ExceptionClass> (SQLSTATE <code>)`, plus `line L, column <name>` when the database reports them. The value is never printed |

In every non-zero case the table keeps the content it had before the run.

## Inspection

```text
python ingest/inspect_export.py DIR [--pattern GLOB]
```

`make inspect SOURCE=data/<folder>` runs it. It needs no database.

For each matching file it prints: the path, the record count, and for every JSON key the number of records that have it, the JSON value types seen (`string`, `number`, `boolean`, `null`, `object`, `array`) and the number of `null` values. It then prints the keys outside the 23 sample fields, the 23 sample fields that are absent, and for each file how many records fill each descriptor group (music, podcast, audiobook, none, several). Non-matching files are listed as ignored. Exit code `0`, or `2` for the same input errors as the loader. Names, counts and types only; never values.

## Acceptance checks

Covered by `tests/test_load_unit.py` and `tests/test_load_db.py`: file discovery and ignored list; record validation messages; text rendering of null, booleans, numbers and strings; error filtering (no value in the output, checked with a planted marker); load into a throwaway all-text table with counts equal per file and in total; `NULL` preservation in the four booleans; reload gives the same rows; a bad file rolls back and leaves the previous content; missing table and missing `source_file` stop before reading data; the inspection report on the sample data.
