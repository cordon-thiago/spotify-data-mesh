# Feature Specification: Raw Ingestion

**Feature Branch**: `002-raw-ingestion`

**Created**: 2026-10-26

**Status**: Draft

**Input**: User description: "Phase 1 Raw ingestion of the Spotify Data Mesh: load the streaming history JSON files into a source-aligned raw table in the local Postgres, keeping the data as it arrives. Concept to learn: source-aligned data and ELT (load first, transform later). Scope: inspect the real export ZIP placed in data/ (file names, schema, which files hold which content type, differences from the 23-field sample schema) and record what was found; a loader (ingest/load.py) that reads the export JSON files (arrays of 23-field records, also the synthetic sample_data/ files), flattens them to CSV and loads them with COPY into a restricted raw.spotify_streams table; the learner writes the table DDL column list and types themselves; the table holds ip_addr and is restricted (owner-only access comes in Phase 2); loading must run on sample_data/ without any real export, and on the real export from data/ without ever committing it; keep null values as null, in particular in the boolean fields; the table is the source for the dbt staging layer in Phase 3. Checkpoint: JSON record count equals table row count, per file and in total; null booleans are preserved and counted. Out of scope: roles and grants (Phase 2), deduplication, timezone conversion, any business rule (Phase 3)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Load the synthetic sample into the raw table (Priority: P1)

The project owner (or a contributor without a Spotify export) runs one command and the synthetic streaming history from Phase 0 ends up in a raw table in the local database, exactly as it is in the files. A check then proves that nothing was lost or changed.

**Why this priority**: It delivers the whole load path and the checkpoint without needing the real export, which the owner has not placed yet. It is also the path every later phase and every contributor uses.

**Independent Test**: With the database running and the table defined, load `sample_data/`. The report shows, for each file and in total, the number of records read equal to the number of rows loaded, and the same count of `null` values in each of the four optional boolean fields on both sides.

**Acceptance Scenarios**:

1. **Given** the database is running and the raw table exists, **When** the owner loads the sample data, **Then** the row count in the table equals the record count of the two sample files, per file and in total.
2. **Given** the sample data contains `null` in `shuffle`, `skipped`, `offline` and `incognito_mode`, **When** it is loaded, **Then** those values are `null` in the table (not `false`, not empty text), and the count of `null` per field matches the files.
3. **Given** the data was already loaded once, **When** the owner loads it again, **Then** the table holds the same rows as after a single load, not double.
4. **Given** the raw table has not been created, **When** the owner runs the load, **Then** it stops before touching any data and tells the owner which file to write and run.
5. **Given** the sample files contain exact duplicate records, **When** they are loaded, **Then** the duplicates are loaded as they are, because removing them belongs to a later phase.

---

### User Story 2 - Inspect the real export and record what it contains (Priority: P2)

The owner places the real export ZIP in the private data folder, inspects it, and writes down what was found: which files exist, how many records each holds, which fields they have, which file holds which content type, and how all of that differs from the 23-field sample schema.

**Why this priority**: The plan and the generator were built from two sample records. Loading the real export on top of wrong assumptions would silently lose or distort data, so the facts must be confirmed first.

**Independent Test**: A findings document exists in the repository, lists every streaming-history file by name pattern with its record count and content type, lists any field that is added, missing or different against the 23-field schema, and contains no personal data.

**Acceptance Scenarios**:

1. **Given** the real ZIP is in the private data folder, **When** the owner follows the inspection steps, **Then** the findings document lists each file pattern, its record count and the content types it holds.
2. **Given** a field in the real export is missing, extra or of a different type than the sample schema, **When** the owner inspects it, **Then** the difference is written in the findings and the table definition and the generator are marked for update.
3. **Given** the findings document, **When** anyone reads it on the public repository, **Then** it contains no real IP address, no track, artist or episode name, and no other listening detail, only structure and counts.
4. **Given** the export contains files that are not streaming history (for example a read-me or account data), **When** the owner inspects it, **Then** the findings list them as excluded from loading, with the reason.

---

### User Story 3 - Load the real export without ever committing it (Priority: P3)

The owner loads the real export from the private data folder into the same raw table, with the same checks, and nothing from it reaches version control, logs or console output.

**Why this priority**: It is the goal of the project, but it depends on the owner having the ZIP, and it only repeats the load path of Story 1 on different input once Story 2 has confirmed the structure.

**Independent Test**: Load the real export, compare the per-file and total counts and the `null` counts with the figures in the findings, then run the repository hygiene check: it finds no real data in tracked files and the load output shows counts only.

**Acceptance Scenarios**:

1. **Given** the real export is extracted in the private data folder, **When** the owner loads it, **Then** the table row count equals the sum of the streaming-history records in the files, per file and in total.
2. **Given** a load of real data finishes or fails, **When** the owner reads the output and logs, **Then** they contain file names and counts only, never field values such as the IP address.
3. **Given** the real export is loaded, **When** the owner checks version control, **Then** no file from the private data folder, no generated intermediate file with real data and no load output with real values is tracked or trackable.
4. **Given** a file in the export fails to load, **When** the load stops, **Then** the table is left as it was before the run (no partial load) and the error names the file.

---

### Edge Cases

- A file is empty or holds an empty array: it loads zero rows and is reported with a count of zero, not skipped silently.
- A file is not valid JSON, is truncated, or is not an array of objects: the load stops and names the file.
- A record has a field the table does not know (the export gained a field), or lacks a known field: the load reports it clearly instead of dropping or inventing data.
- A boolean field arrives as text such as `"true"`, or a number field as text: the load reports the mismatch with the file name and does not coerce silently.
- A record has `ms_played` or `ts` that look wrong (negative, far in the future): they are loaded as they are, because validation is a later phase.
- Files are large (a long listening history can reach millions of records): the load completes without holding the whole export in memory.
- The load is interrupted midway (database stopped, disk full): the table is not left with a partial load.
- The private data folder holds the ZIP but it is not extracted: the load explains how to extract it into the private folder.
- Two files hold overlapping periods: both are loaded as they are, and overlaps are handled in Phase 3.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST provide a single documented command that loads the streaming-history JSON files from a chosen folder into the raw table, and the same command MUST work on the synthetic sample folder and on the private data folder.
- **FR-002**: The raw table definition (column list and types) MUST be written by the owner, in a tracked SQL file, and the loader MUST NOT create or alter the table. If the table is missing, the loader MUST stop before reading data and name the file to write and run.
- **FR-003**: The raw table MUST keep the data as it arrives: every field of every record is stored without trimming, renaming of values, conversion of business meaning, deduplication, filtering or time-zone conversion.
- **FR-004**: The table MUST represent absent values as database `NULL`, and the optional boolean fields (`shuffle`, `skipped`, `offline`, `incognito_mode`) MUST be stored so that `null`, `false` and `true` stay distinguishable.
- **FR-005**: Every loaded row MUST be traceable to the source file it came from, so that row counts can be checked per file.
- **FR-006**: After each load the loader MUST report, per file and in total, the number of records read, the number of rows loaded, and the number of `null` values in each of the four optional boolean fields on both sides, and MUST fail with a non-zero exit code if any pair differs.
- **FR-007**: A load MUST be all-or-nothing: if any file fails, the table keeps its state from before the run.
- **FR-008**: Loading the same input twice MUST leave the table with the same rows as loading it once (a run replaces the previous content of the table).
- **FR-009**: The loader MUST stop with a clear message, naming the file, when a file is not valid JSON, is not an array of records, or when a record has fields that the table does not define or lacks fields it requires.
- **FR-010**: The loader MUST process files without loading a whole export in memory at once.
- **FR-011**: The loader MUST select streaming-history files by a documented file-name rule taken from the inspection findings, and MUST list any other file it ignores.
- **FR-012**: The loader's console output and logs MUST contain file names, counts and error categories only, and MUST NOT print or log field values.
- **FR-013**: Intermediate files created during loading MUST be written inside the private data folder or removed after the load, so they cannot be tracked by version control.
- **FR-014**: The project MUST include a findings document for the real export, listing each streaming-history file pattern with its record count and content type, every field that is added, missing or different from the 23-field schema, and the files excluded from loading. It MUST contain no personal data.
- **FR-015**: If the inspection finds differences from the 23-field schema, the owner's table definition, the loader's file rule, and the sample data generator MUST be updated to match before the real export is loaded.
- **FR-016**: Roles, grants, access restrictions, deduplication, time-zone conversion and any business rule are out of scope: this feature MUST NOT implement them. The raw table is restricted by a later phase, and until then only the owner connects to the database.

### Key Entities

- **Export file**: one JSON file of the export, holding an array of stream records, with a name, a record count and a content type (music, podcast, audiobook or mixed).
- **Raw stream record**: one row of the raw table, the stored image of one JSON record, plus the identity of the file it came from. It contains the restricted IP field.
- **Load run**: one execution of the loader over a folder, with per-file and total counts of records read and rows loaded, and the `null` counts of the optional boolean fields.
- **Export findings**: the written description of the real export (files, counts, content types, schema differences, excluded files), free of personal data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the sample data and for the real export, the number of rows loaded equals the number of records in the files in 100% of loads, per file and in total.
- **SC-002**: In 100% of loads, the count of `null` in each of the four optional boolean fields in the table equals the count in the source files.
- **SC-003**: Loading the default sample dataset (2,000 records) completes in under 30 seconds from a running database.
- **SC-004**: The real export loads in under 10 minutes on the owner's laptop, whatever its size, without running out of memory.
- **SC-005**: Re-running a load leaves the row count unchanged in 100% of re-runs.
- **SC-006**: A load that fails leaves the table as it was before the run in 100% of failures, and the error names the file at fault.
- **SC-007**: A search of the repository (files and history) after loading the real export finds 0 real IP addresses, listening-history records or intermediate files with real values.
- **SC-008**: The owner can explain, from the findings document and the README alone, what "source-aligned" and "load first, transform later" mean for this table (learning checkpoint).

## Assumptions

- Phase 0 is complete: the local database and the Python environment work, and the synthetic sample files exist with the 23-field schema.
- The owner has not yet placed the real ZIP in the private data folder. Stories 1 and 3 can be completed in the order 1, then 2 and 3 when the ZIP arrives.
- The owner extracts the ZIP into a subfolder of the private data folder; the loader reads extracted JSON files, not the ZIP itself.
- The table definition is the owner's learning exercise: the assistant describes the data and explains the choices, but does not write the column list and types.
- A run replaces the previous content of the table (full reload) rather than appending. Appending several exports is out of scope.
- The table lives in a `raw` schema under the name `spotify_streams`, which matches the project plan, and the `raw` schema is created together with the owner's table definition.
- File names and content types of the real export are unknown until inspection. The file-name rule in FR-011 is written after Story 2; the sample files use the Phase 0 names.
- Until Phase 2, the database has only the `owner` user, so the raw table is accessible to the owner only by construction, not by grants.
- The Postgres adapter in dbt v2 is experimental (ADR 0001); this phase does not use dbt.
