# Contract: raw table conventions

What the loader relies on in `raw.spotify_streams`. These are **conventions**, not a definition: the column list, the types, the nullability and any constraints are written by the owner in `sql/raw_spotify_streams.sql` (✍️ in the implementation plan). Satisfies FR-002 to FR-005.

## Where

| Item | Value |
| --- | --- |
| Schema | `raw` (created by the owner's SQL file) |
| Table | `spotify_streams` |
| Definition file | `sql/raw_spotify_streams.sql`, tracked, written by the owner |
| Applied with | `make raw-table` |

`sql/raw_spotify_streams.sql` ships as a stub containing only comments. The loader refuses to run until the owner has replaced it with a real definition and applied it.

## What the loader requires

1. **One column per JSON field, with the same name as the key.** The JSON keys of the export are the source of the names (for the samples: the 23 fields listed in the Phase 0 data model).
2. **A column named `source_file`.** The loader fills it with the file's path relative to the source folder.
3. **Any other column must be filled by the database itself**: it has a default, is an identity column or is generated (for example a row id or a load timestamp). The loader never writes to such columns.
4. **The table is not altered or created by the loader.** It only empties it (`TRUNCATE`) and fills it.

## What the owner decides

- The type of each column (including how to keep `null`, `false` and `true` apart for the four optional boolean fields).
- Nullability, defaults, constraints and indexes.
- Any extra columns that follow rule 3.

## How the loader reads the table

The loader lists the table's columns from the database catalog. **Data columns** are the columns without a default that are not identity or generated, excluding `source_file`. Every record's keys must equal the set of data columns exactly.

| Situation | Result |
| --- | --- |
| Table or schema missing | Stop before reading data; message names `sql/raw_spotify_streams.sql` and `make raw-table` |
| `source_file` column missing | Stop before reading data; message names the column |
| A record has a key with no matching data column (new field in the export) | Stop; message names the file and the key |
| A record lacks a key that a data column expects | Stop; message names the file and the column |
| A value does not fit the column type | The copy fails and rolls back; message names the file, the line and the column, never the value |

## Value fidelity

The loader sends each JSON value as text and lets Postgres convert it (see [data-model.md](../data-model.md), Value fidelity). `null` always arrives as SQL `NULL`.

## Privacy

`ip_addr` is restricted data. Until Phase 2 the table is owner-only because only the `owner` user exists. The Phase 2 ODCS contract will record the classification of every column; this phase only guarantees the loader prints no values.
