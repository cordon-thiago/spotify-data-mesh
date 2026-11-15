# sql

Database setup scripts. Privacy is enforced here, by permission, not by prompt.

| File | What it does | Apply with |
| --- | --- | --- |
| `raw_spotify_streams.sql` | Creates schema `raw` and the table `raw.spotify_streams` (drops and recreates it) | `make raw-table` |
| `roles.sql` | Creates the layers `staging`, `marts`, `semantic`, the roles `dbt` and `agent`, and all grants. Safe to run again; it also resets the two passwords | `make roles` |

Order on a clean machine: `make raw-table`, `make roles`, `make load`. Recreating the raw table later does not need `make roles` again: default privileges keep `dbt` able to read it.

| Role | Can do |
| --- | --- |
| `owner` | Everything; the only role that writes raw data |
| `dbt` | Read `raw`; build in `staging`, `marts`, `semantic` |
| `agent` | Read `marts` and `semantic`. No grant at all on `raw` and `staging`, so `SELECT ip_addr` is refused |

The full matrix the tests check is in [specs/003-roles-and-grants/contracts/roles-and-grants.md](../specs/003-roles-and-grants/contracts/roles-and-grants.md). The passwords come from `DBT_PASSWORD` and `AGENT_PASSWORD` in `.env`.

Known limits: `dbt` owns what it builds, so it could expose a restricted field in a mart (the Phase 4 test guards this), and `agent` can still see object names, not values, in the database catalog.
