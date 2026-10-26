# ingest

Tools that bring the Spotify export into the database (Phase 1).

| Script | What it does |
| --- | --- |
| `load.py` | Loads the streaming-history JSON files from a folder into `raw.spotify_streams`, unchanged. It reads one file at a time and streams the rows into Postgres with `COPY`. In one transaction it empties the table, loads every file, compares the counts with the source and commits only if they all match. |
| `inspect_export.py` | Prints the structure of an export folder: files, record counts, keys, JSON types, null counts and content types. It never prints values, so it is safe to run on the real export. |

## Make targets

| Target | Does |
| --- | --- |
| `make raw-table` | Apply your table definition from `sql/raw_spotify_streams.sql` |
| `make load` | Load `sample_data/` (the synthetic data) |
| `make load SOURCE=data` | Load the real export from the private `data/` folder |
| `make inspect SOURCE=data` | Show the structure of the real export |

## Rules

- The loader never creates or alters the table. The column list and types are the owner's, see [../sql/raw_spotify_streams.sql](../sql/raw_spotify_streams.sql).
- A run replaces the table content, and a failed run leaves the table as it was.
- Output and logs contain file names, counts and error categories only, never field values.
- Nothing is written to disk besides the database: there is no intermediate CSV.

Design: [specs/002-raw-ingestion/](../specs/002-raw-ingestion/).
