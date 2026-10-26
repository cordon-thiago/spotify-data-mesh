# Feature Specification: Local Development Foundation

**Feature Branch**: `001-local-dev-foundation`

**Created**: 2026-10-25

**Status**: Draft

**Input**: User description: "Phase 0 Foundation of the Spotify Data Mesh: a reproducible local environment. Folder structure from the implementation plan; English README; Postgres via docker compose; Python virtualenv with dbt v2; sample_data/ with a synthetic generator producing the 23 fields of the Spotify extended streaming history export, as shown in the owner's real samples (also the pipeline test fixture); data/ kept out of git. Learning goal: why raw data stays out of git, Docker/Postgres basics. Checkpoint: docker compose up and psql connect; sample data generated."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bring up the local environment from a clean clone (Priority: P1)

The project owner (or anyone who clones the public repository) follows the README on a machine that has only the documented prerequisites and ends up with a running local database and a working Python toolchain, without touching any personal data.

**Why this priority**: Every later phase (ingestion, governance, dbt, eval) depends on a database that starts the same way every time. Without it nothing else can be built or verified.

**Independent Test**: On a clean clone, follow only the README: start the services, then connect to the database with a command-line client. The connection succeeds and a trivial query returns a result.

**Acceptance Scenarios**:

1. **Given** a clean clone with prerequisites installed, **When** the owner follows the README setup steps, **Then** the database service starts and accepts a connection from a command-line client.
2. **Given** the services are running, **When** the owner stops and restarts them, **Then** the database comes back with the same connection settings and no manual repair.
3. **Given** the Python environment is created as documented, **When** the owner runs the transformation tool's version command, **Then** it reports an installed version.
4. **Given** the database port or the service name is already in use on the machine, **When** the owner starts the services, **Then** the README tells them how to resolve it.

---

### User Story 2 - Generate synthetic sample data with the real export schema (Priority: P2)

The owner (or a contributor without a Spotify export) runs one command and gets a synthetic streaming-history dataset with the same 23 fields as the real export. It is the stand-in for personal data in every test and demo.

**Why this priority**: The constitution requires the whole pipeline to run on sample data alone. Later phases need a fixture that already contains the known traps of the export.

**Independent Test**: Run the generator twice with the same settings. Both runs produce identical files, each record has all 23 fields, and the output contains the documented edge cases.

**Acceptance Scenarios**:

1. **Given** a configured environment, **When** the owner runs the generator, **Then** sample files appear in `sample_data/` with one record per stream and all 23 export fields present in each record.
2. **Given** the same settings are used twice, **When** the generator runs both times, **Then** the output is byte-for-byte identical.
3. **Given** the generated data, **When** the owner inspects it, **Then** it contains music, podcast and audiobook streams, `null` values in the optional boolean fields, private-session records, streams that cross midnight in local time, and records with the restricted IP field filled with an obviously fake value.
4. **Given** a different seed or size setting, **When** the generator runs, **Then** it produces a different dataset of the requested size with the same schema.

---

### User Story 3 - Understand why raw data stays out of git (Priority: P3)

The owner, who is learning, reads the README and the project layout and can explain, and verify, why the real export never enters version control while synthetic data does.

**Why this priority**: This is the phase's learning checkpoint, and it protects the owner's privacy in a public repository, but it adds no runtime capability.

**Independent Test**: Place a dummy file in the raw-data folder and check that version control ignores it; the README section explains the reasoning in plain language.

**Acceptance Scenarios**:

1. **Given** a file placed in the raw-data folder, **When** the owner checks the repository status, **Then** the file does not appear as trackable.
2. **Given** the README, **When** the owner reads the data-handling section, **Then** it states what is committed (code, contracts, eval questions, synthetic data) and what is never committed (the real export), with the reason.
3. **Given** a fresh clone of the public repository, **When** anyone searches it, **Then** they find no real IP address or listening history.

---

### Edge Cases

- The machine has no container runtime or an unsupported Python version: the README lists the prerequisites and the failure is visible and understandable, not silent.
- The database was started before and holds old data: the README explains how to reset to a clean state.
- The generator is asked for zero or a very large number of records: it rejects invalid input with a clear message and handles large sizes without running out of memory on a normal laptop.
- The real export is dropped into the raw-data folder before the ingestion phase exists: it stays ignored by version control and is not touched by any command in this phase.
- A contributor on a different operating system follows the README: the steps do not depend on a single OS beyond the documented prerequisites.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST contain the folder structure defined in the implementation plan (raw data, sample data, contracts, transformation project, agent, eval with reports, docs), each folder present and explained, so later phases have a place to land.
- **FR-002**: The repository MUST include an English README covering prerequisites, setup, how to start and stop the services, how to reset them, how to generate sample data, and the data-handling policy.
- **FR-003**: A single documented command MUST start a local relational database that accepts connections from a command-line client, using documented connection settings.
- **FR-004**: Database connection settings MUST be configurable without editing tracked files, and any credential used for local development MUST NOT be a real secret.
- **FR-005**: Database data MUST persist across a stop and restart, and a documented command MUST reset it to a clean state.
- **FR-006**: A documented procedure MUST create an isolated Python environment containing the transformation tool, able to target the project database, with pinned dependency versions.
- **FR-007**: A synthetic-data generator MUST produce streaming-history records containing all 23 fields of the Spotify extended streaming-history export, with field names and value shapes matching the owner's real samples (for example `ip_addr`, `offline_timestamp` as epoch seconds, and the four `audiobook_*` fields), laid out as files that each hold a JSON array of records.
- **FR-008**: The generator MUST be deterministic: the same settings and seed produce identical output.
- **FR-009**: The generator MUST let the user choose the number of records and the seed.
- **FR-010**: The generated data MUST include music, podcast and audiobook streams, `null` in the optional boolean fields, private-session records, streams crossing local midnight, and repeated records usable to test deduplication.
- **FR-011**: The restricted field in synthetic data (IP address) MUST use reserved or clearly fake values that cannot identify a real person or device. If the generator ever emits a user agent or username field, it MUST apply the same rule.
- **FR-012**: The raw-data folder MUST be excluded from version control, and the synthetic sample folder MUST be tracked.
- **FR-013**: The synthetic data and the generator MUST be usable as the test fixture for later pipeline phases without modification of their schema.
- **FR-014**: Nothing in this phase MUST read, copy, transform or transmit a real Spotify export.

### Key Entities

- **Stream record**: one playback event with 23 attributes, including end timestamp (UTC), milliseconds played, track, artist and album descriptors, episode descriptors, audiobook descriptors, start and end reasons, optional boolean flags, an offline timestamp in epoch seconds, platform, connection country, and one restricted identifier (IP address). Music, podcast and audiobook streams populate different descriptor fields and leave the others `null`.
- **Sample dataset**: a deterministic collection of stream records in the same file layout as the real export, identified by its seed and size.
- **Local environment**: the running database service plus the Python toolchain, described entirely by tracked files and documented commands.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a clean clone, a person with the documented prerequisites reaches a working database connection in under 15 minutes by following only the README.
- **SC-002**: After the services are started, a client connection succeeds within 1 minute, and 100% of restarts keep the same connection settings.
- **SC-003**: The generator produces a default dataset in under 30 seconds on a normal laptop, and two runs with the same settings produce identical output 100% of the time.
- **SC-004**: 100% of generated records contain all 23 fields, and the dataset contains every edge-case category listed in FR-010.
- **SC-005**: A search of the full repository history finds 0 real IP addresses or listening-history records.
- **SC-006**: The owner can state, from the README alone, what is and is not committed and why, with no further explanation (learning checkpoint).

## Assumptions

- The owner already has a container runtime, a compatible Python version and a command-line database client available, or the README tells them how to get them; installing them is outside this feature.
- The technology choices come from the constitution and the implementation plan: a local Postgres database run with containers, Python with dbt v2 (open-source runtime, Postgres adapter still experimental, chosen by the owner; see ADR 0001). This spec states outcomes; the plan step chooses concrete versions and file layout.
- The field list and value shapes come from two real record samples supplied by the owner (an audio record and a video record), which share one 23-field schema. They differ from the export description used in the first draft of the plan (21 fields with `ip_addr_decrypted`, `user_agent_decrypted` and `username`): the real export has no user agent or username, names the IP field `ip_addr`, and adds the four `audiobook_*` fields. Real file names and sizes are confirmed against the ZIP in Phase 1, not here.
- In the owner's samples, podcast episodes appear in the "video" example, not the "audio" one. The generator mirrors that split (music and audiobook streams in audio-style files, episodes in video-style files) until Phase 1 confirms which real files hold which content types.
- `offline_timestamp` is epoch seconds and is not necessarily close to `ts`, so the generator does not derive one from the other.
- Loading data into the database, roles and grants, contracts and dbt models are out of scope: they belong to Phases 1 to 4.
- The README and all repository content are in English, per the constitution.
- Dependency and image versions will be pinned during planning so that results are reproducible.
- The spec directory is `specs/001-local-dev-foundation`; no feature branch was created and work continues on `main` unless the owner decides otherwise.
