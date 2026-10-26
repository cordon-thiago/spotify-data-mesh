# Data Model: Raw Ingestion

Entities from the spec. **No column types appear here on purpose**: the table definition is the owner's exercise (see [contracts/raw-table-conventions.md](contracts/raw-table-conventions.md)). Field names and meaning come from the Phase 0 [data model](../001-local-dev-foundation/data-model.md); the real export may differ, which the inspection records.

## Export file

One JSON file holding an array of stream records.

| Attribute | Rule |
| --- | --- |
| Path | Relative to the chosen source folder; used as the file's identity and stored as `source_file` |
| Selection | Matches `streaming_history_*.json`, case-insensitive, recursively (see research, section 10) |
| Content | A JSON array; every element is an object whose keys equal the table's data columns |
| Content type | Music, podcast, audiobook or mixed, from which descriptor fields are filled (reported by the inspection, not stored) |
| Empty file | A valid empty array is allowed: zero rows, reported with count 0 |

### Validation rules (enforced by the loader)

- Top level is an array of objects, else the load stops naming the file.
- Each record's keys equal the table's data columns exactly (no extra, none missing).
- No value is altered, trimmed, coerced or validated for business meaning.

## Raw stream record

One row of `raw.spotify_streams`: the stored image of one JSON record plus its origin.

| Part | Source | Rule |
| --- | --- | --- |
| One column per JSON field (23 in the samples) | The record | Same name as the key; the value is stored as the source gave it. JSON `null` is SQL `NULL` |
| `source_file` | The loader | Relative path of the file the row came from |
| Owner-chosen extras (row id, load time) | The database | Must have a default, identity or generated value so the loader leaves them alone |

Restricted data: the `ip_addr` column holds an IP address. The table is owner-only by construction until Phase 2 adds roles.

### Value fidelity

| JSON value | Sent to the database as |
| --- | --- |
| `null` | SQL `NULL` |
| `true` / `false` | the text `true` / `false` |
| number | its decimal text |
| string | the string, unchanged (an empty string stays empty, distinct from `NULL`) |

The column types chosen by the owner decide how Postgres stores these. A value that does not fit the chosen type fails the load.

## Load run

One execution of the loader.

| Attribute | Meaning |
| --- | --- |
| Source folder | Folder searched for export files |
| Target table | Default `raw.spotify_streams` |
| Per file | Records read; rows loaded; `NULL` count for each of `shuffle`, `skipped`, `offline`, `incognito_mode`, on the read side and on the table side |
| Total | Sums of the same figures |
| Ignored files | Files found but not matching the rule |
| Outcome | `committed` when every pair of figures matches; otherwise `rolled back` with the reason |

### State transitions

```text
start → table checked → table emptied (in a transaction)
      → file 1 loaded → … → file N loaded
      → counts compared → committed
any failure at any step → rolled back (table as before the run)
```

## Export findings

A written description of the real export, free of personal data.

| Section | Content |
| --- | --- |
| Files | Name pattern, record count and content type for each streaming-history file |
| Excluded | Files not loaded and why |
| Schema | Fields added, missing or of a different JSON type than the 23-field sample schema |
| Size | Total records and largest file size |
| Decisions | Updates needed to the owner's table definition, the file rule and the generator |

### Relationships

- A **Load run** reads many **Export files** and produces rows in the table, each row pointing back to its **Export file** through `source_file`.
- The **Export findings** describe the **Export files** of the real export and decide the final file rule and table definition.
