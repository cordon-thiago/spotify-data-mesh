# Contract: roles and grants

The permission matrix `sql/roles.sql` must produce and `tests/test_roles_db.py` must assert. Satisfies FR-001 to FR-010 and FR-018. "refused" means `InsufficientPrivilege` (SQLSTATE 42501).

## Interface

| Item | Value |
| --- | --- |
| Script | `sql/roles.sql`, run as `owner` |
| Command | `make roles` |
| Inputs | `DBT_PASSWORD`, `AGENT_PASSWORD` from `.env` or the environment; missing value stops with a clear message before any change |
| Idempotent | yes; second run changes nothing but resets the two passwords to the current settings |
| Output | role and layer names and a final line per check; no passwords |

## Matrix asserted by the tests

| Action | `owner` | `dbt` | `agent` |
| --- | --- | --- | --- |
| `SELECT ip_addr` from a raw table | allowed | allowed | refused |
| `SELECT *` from a raw table | allowed | allowed | refused |
| Read a staging object | allowed | allowed | refused |
| Read a `dbt`-built marts or semantic object | allowed | allowed | allowed, with no new grant |
| Create a view in staging | allowed | allowed | refused |
| Create or replace a table in marts and semantic | allowed | allowed | refused |
| Insert, update, delete, truncate on a raw table | allowed | refused | refused |
| Drop a raw table | allowed | refused | refused |
| Create any object in raw | allowed | refused | refused |
| `GRANT SELECT` on a raw table | allowed | refused | refused |
| `CREATE ROLE` | allowed | refused | refused |
| Create a temporary table | allowed | allowed | refused |
| Read a raw table after it was dropped and recreated by `owner` | allowed | allowed | refused |

## Rerun behavior

| Situation | Result |
| --- | --- |
| Run on a fresh database | Layers, roles, grants and default privileges exist |
| Run twice | No error; same grants |
| Run before the raw table exists | Succeeds; `dbt` can read the table when created later |
| A password is missing | Stops before changing anything; message names the missing setting |
