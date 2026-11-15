# Feature Specification: Roles and Base Governance

**Feature Branch**: `003-roles-and-grants`

**Created**: 2026-11-15

**Status**: Draft

**Input**: User description: "Phase 2: Roles and base governance (privacy by permission, not by prompt). Postgres roles owner, dbt, agent; schemas raw, staging, marts, semantic; GRANTs in sql/roles.sql; ODCS contract contracts/spotify_streams.odcs.yaml with per-field classification (ip_addr = restricted; the real export has no user agent or username field). Checkpoint: as agent, SELECT ip_addr fails."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The agent role cannot read the IP address (Priority: P1)

The project owner runs one command that sets up the database layers and the three roles. After that, connected as the agent role, any attempt to read `ip_addr` fails with a permission error, whether it is asked directly, through `SELECT *`, or by naming the raw table. Connected as the owner, the same data is readable.

**Why this priority**: It is the checkpoint of the phase and the core guarantee of the project (Principle I). Every later phase, and the whole agent evaluation, relies on it. Nothing else in this phase matters if this fails.

**Independent Test**: With the raw table loaded from the sample data, connect as the agent role and run `SELECT ip_addr FROM raw.spotify_streams`, `SELECT * FROM raw.spotify_streams` and a read of any table in `staging`. Each read fails with a permission error. Connect as the owner and the first query returns rows.

**Acceptance Scenarios**:

1. **Given** the layers and roles are set up and the raw table is loaded, **When** the agent role selects `ip_addr` from the raw table, **Then** the database refuses with a permission error and returns no rows.
2. **Given** the same setup, **When** the agent role selects every column of the raw table, **Then** the database refuses as well; no partial result is returned.
3. **Given** the same setup, **When** the agent role tries to read the staging layer, **Then** it is refused, because only the marts and the semantic layer are open to it.
4. **Given** the same setup, **When** the owner role selects `ip_addr`, **Then** the rows are returned, so the restriction is a permission and not a missing column.
5. **Given** the agent role has read access to a mart or semantic object, **When** it tries to insert, update, delete, create or drop anything, **Then** the database refuses; the agent is read-only.

---

### User Story 2 - The pipeline role can build the layers and nothing more (Priority: P2)

The transformation tool connects as the dbt role. It reads the raw table, creates and replaces objects in the staging, marts and semantic layers, and can read what it builds. It cannot change or remove the raw table, it cannot change roles, and it cannot grant access to the raw table or to the layers themselves.

**Why this priority**: Phase 3 starts with the dbt role. Without it, dbt would run as the owner, and the separation between "who builds" and "who owns the source" would be lost before it was ever used.

**Independent Test**: Connected as the dbt role, create a view in staging and a table in marts, read them back, and read the raw table. Then try to delete a raw row, drop the raw table and grant the agent role access to the raw table; all three are refused.

**Acceptance Scenarios**:

1. **Given** the roles are set up, **When** the dbt role reads the raw table, **Then** it succeeds; the raw table is the source of the pipeline.
2. **Given** the roles are set up, **When** the dbt role creates a view in staging, a table in marts and an object in semantic, **Then** each succeeds, and it can replace them on the next run.
3. **Given** the roles are set up, **When** the dbt role tries to insert into, update, delete from, truncate or drop the raw table, **Then** each is refused.
4. **Given** the dbt role has created a new table in marts, **When** the agent role reads it, **Then** it succeeds without anyone granting access again, so the agent sees new curated products without a manual step.
5. **Given** the dbt role has created a new object in staging, **When** the agent role reads it, **Then** it is refused.

---

### User Story 3 - A data contract classifies every field of the raw stream (Priority: P3)

The owner opens one contract file for the raw streaming-history product and sees, for each field, its meaning, type and classification (restricted, confidential or internal), together with who may read the product. `ip_addr` is restricted; `conn_country` is confidential; the rest are internal. The file passes the Data Contract CLI's validation.

**Why this priority**: The roles enforce the rule; the contract documents it and gives later phases something machine-checkable (the privacy CI test in Phase 4, the descriptions for configuration B). It depends on knowing the real field list, which Phase 1 settled, but nothing in Story 1 or 2 depends on it.

**Independent Test**: Run the Data Contract CLI lint on the contract: it passes. Compare the contract's field names with the columns of the raw table: they match one to one. Check that every field has a classification and that exactly one field is restricted.

**Acceptance Scenarios**:

1. **Given** the contract, **When** it is validated with the Data Contract CLI, **Then** validation passes with no errors.
2. **Given** the contract and the raw table, **When** their field lists are compared, **Then** every raw column appears in the contract with the same name and a matching type, and the contract has no field the table lacks.
3. **Given** the contract, **When** each field is read, **Then** it carries a description and exactly one classification from restricted, confidential or internal.
4. **Given** the contract, **When** the owner reads the classification of `ip_addr`, **Then** it is restricted, with the reason (direct identifier) and the access rule (owner and the pipeline only; never curated, never the agent).
5. **Given** the real export has no user agent or username field, **When** the contract is read, **Then** it lists no such field and states that any such field added by a future export is restricted by default.
6. **Given** the contract, **When** it is read for the four nullable booleans, **Then** it states that `null` is a valid value and means "unknown", not `false`.

---

### User Story 4 - Setup is repeatable from nothing (Priority: P3)

A contributor with no real data resets the database, runs the setup, loads the sample, and gets the same roles, layers and permissions as the owner, with every check of the earlier stories passing. Running the setup a second time changes nothing and does not fail.

**Why this priority**: Principle V requires the whole pipeline to run on the sample alone, and a permission setup that only worked once on one machine would not be a guarantee.

**Independent Test**: Reset the database, run setup, load the sample, and run the privacy checks of Story 1 and 2 as an automated test. Run setup again and rerun the test.

**Acceptance Scenarios**:

1. **Given** a freshly reset database, **When** setup is run and the sample is loaded, **Then** all permission checks pass.
2. **Given** setup has already been run, **When** it is run again, **Then** it finishes without error and the permissions are the same as after the first run.
3. **Given** the roles need credentials, **When** setup is run, **Then** passwords come from local settings that are not committed, and the repository contains no password.
4. **Given** the table for raw data is dropped and recreated (as the raw table script does), **When** the agent and dbt roles then read it, **Then** the agent is still refused and the dbt role can still read, with no extra step.

---

### Edge Cases

- The raw table is recreated after the grants were applied (the table script drops and recreates it): its permissions must not leak to other roles, and the dbt role must keep read access without a manual step.
- Someone adds a new column to the raw table in the future: the agent must be refused on it, because the agent has no grant on the raw layer at all, not on a column list that would need updating.
- The agent role is given access to a staging object by mistake: the permission test must catch it.
- A role is asked to read a table that does not exist: it must get the normal "does not exist" or permission error, never data.
- The setup runs before the raw table exists: it must still succeed for the roles and layers, and the dbt role must get read access to the table when it is created later.
- The contract and the table drift apart (a column added to one only): the comparison check must fail and name the field.
- A restricted field is mislabeled as internal in the contract: nothing in this phase detects it automatically; this is the purpose of the Phase 4 privacy test, and the limitation is written down.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The database MUST have four layers: `raw` (source-aligned, restricted), `staging` (cleaned, one-to-one with the source), `marts` (curated products) and `semantic` (governed metrics for the agent).
- **FR-002**: The database MUST have three roles with distinct purposes: `owner` (owns everything, sees the raw layer), `dbt` (builds the layers) and `agent` (reads curated data only).
- **FR-003**: The `agent` role MUST be refused on every read of the `raw` layer, including `ip_addr`, whole-row reads and any future column added to the raw table.
- **FR-004**: The `agent` role MUST be refused on the `staging` layer, and MUST be able to read the `marts` and `semantic` layers.
- **FR-005**: The `agent` role MUST be read-only: it MUST NOT be able to insert, update, delete, truncate, create or drop anything in any layer.
- **FR-006**: The `dbt` role MUST be able to read the raw table, and MUST be able to create, replace and read objects in the `staging`, `marts` and `semantic` layers.
- **FR-007**: The `dbt` role MUST NOT be able to modify, truncate or drop the raw table, MUST NOT be able to create objects in the `raw` layer, MUST NOT be able to create or alter roles, and MUST NOT be able to grant access on the raw table or on any layer. It owns the objects it builds, so it can grant on those; the agent's access to them is therefore guarded by the Phase 4 privacy test, not by this phase (see Assumptions).
- **FR-008**: Objects the `dbt` role creates in `marts` and `semantic` MUST be readable by the `agent` role automatically, without a manual grant per object. Objects it creates in `staging` MUST NOT be.
- **FR-009**: Nothing outside the three roles MUST have access to any layer: access given to everyone by default MUST be removed from the layers and the database objects this project creates.
- **FR-010**: Setup MUST be a single command that creates the layers, roles and grants, MUST be safe to run repeatedly, and MUST work on a freshly reset database.
- **FR-011**: Role passwords MUST come from local settings that are git-ignored; the repository MUST publish only an example of the settings, with no real password. The example file MUST list the new settings.
- **FR-012**: The repository MUST contain a data contract for the raw streaming-history product that declares, for every field of the raw table: name, type, description and a classification of `restricted`, `confidential` or `internal`.
- **FR-013**: The contract MUST classify `ip_addr` as restricted, `conn_country` as confidential and every other field as internal, following the table in `.claude/plans/business-rules.md`.
- **FR-014**: The contract MUST state who may read the product (owner and the pipeline) and that the `agent` role has no access to it.
- **FR-015**: The contract MUST state that the export has no user agent or username field, and that any such field in a future export is restricted by default.
- **FR-016**: The contract MUST pass the Data Contract CLI's validation.
- **FR-017**: A repeatable automated check MUST confirm that the contract's field list and types match the raw table, and MUST fail naming the field when they differ.
- **FR-018**: A repeatable automated check MUST confirm every permission acceptance scenario of Stories 1 and 2, by connecting as each role. It MUST run on the sample data alone.
- **FR-019**: Setup and checks MUST NOT print, log or commit any real field value; the checks MUST use only counts and error classes.
- **FR-020**: When the raw table is dropped and recreated (as its table script does), it MUST stay closed to everyone but the owner and the `dbt` role, and the `dbt` role MUST be able to read it again without rerunning setup.

### Key Entities

- **Layer**: A named area of the database with one purpose and one audience. Four exist: raw, staging, marts, semantic. Attributes: who may read it, who may write to it.
- **Role**: A database identity with fixed powers. Three exist: owner, dbt, agent. Attributes: the layers it can read, the layers it can write, whether it can change grants.
- **Data contract**: A file that describes one data product: its fields, their types, meanings and classifications, who may access it and what the product guarantees. Attributes: product name, version, owner, per-field classification, access rule.
- **Classification**: A label on a field that says how sensitive it is. Three values: restricted (direct identifier, never leaves the raw layer), confidential (kept, shared with care), internal (ordinary). Attribute: the reason for the label.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: As the agent role, 100% of attempts to read `ip_addr` fail (direct, whole-row and through any layer other than marts and semantic), tested on at least these four forms: named column, `SELECT *`, the raw table by qualified name, and the staging layer.
- **SC-002**: As the dbt role, a complete build cycle (create a staging view, create a marts table, read both, read raw) succeeds, and all four forbidden actions (modify raw rows, drop the raw table, create in raw, change a grant) fail.
- **SC-003**: Setup runs from a freshly reset database to a verified state in one command and under 1 minute, and a second run completes with no error and no change in permissions.
- **SC-004**: The contract describes 100% of the raw table's fields with one classification each, exactly one of them restricted, and passes validation with zero errors.
- **SC-005**: The automated permission checks and the contract-versus-table comparison run on the sample data alone, with no real export present, and pass.
- **SC-006**: A search of every tracked file and every command output of this phase finds no real password, no real IP address and no real listening detail.

## Assumptions

- The database runs locally and only the owner (the project's own database user) exists today. `owner` is that user and is not created, only documented and used.
- The three roles are database login roles, each with its own password from local settings. The `agent` password is never given to any tool except the agent's own connection, which is built in a later phase.
- The `dbt` role owns the tables and views it builds, as dbt requires, so it can grant on them. This phase cannot prevent that; it guarantees only that `dbt` cannot grant on the raw table or the layers. A curated object that exposes a restricted field is caught by the Phase 4 privacy test.
- The agent can still see object names, including the name `ip_addr`, in the database's catalog; it cannot read any value. Hiding names is not a goal.
- Access is granted by layer, not by column: the agent has no grant on `raw` or `staging` at all, so a column added later cannot leak. Column-level grants are not used.
- Layer names and the roles-to-layers table follow `.claude/plans/business-rules.md` and Principle I of the constitution. The `intermediate` models of the plan live in a dbt folder and, when they need storage, in `staging`; a separate layer for them is not created in this phase.
- The dbt role reads the raw table because the constitution makes the deduplication step (`int_streams_deduplicated`) the only door from the restricted layer to the marts; that the step drops `ip_addr` is tested in Phases 3 and 4, not here.
- Row limits and the agent's audit log belong to the phase where the agent is built (Phase 6). This phase only guarantees what the role can reach.
- The Data Contract CLI is available to contributors as a project development tool; installing it is part of this phase.
- Contracts for the other two products (`listens`, `listened_catalog`) and the CI test that fails when a restricted field appears in a mart are Phase 4, not here.
- Out of scope: encryption at rest, network access rules, row-level security, SSL and password rotation. The database is bound to the local machine only.
