# contracts

One ODCS data contract (YAML) per data product: `spotify_streams` (Phase 2), then `listens` and `listened_catalog` (Phase 4). The Data Contract CLI validates the files.

Every property carries a classification:

| Classification | Meaning | Example |
| --- | --- | --- |
| `restricted` | Direct identifier or personal data. Owner and `dbt` only; never in a mart, the semantic layer or the agent. | `ip_addr` |
| `confidential` | Kept in curated products, shared with care. | `conn_country` |
| `internal` | Ordinary listening data. | track, artist, `ts`, `ms_played` |

```bash
make lint-contract        # validate contracts/spotify_streams.odcs.yaml
uv run pytest tests/test_contract.py   # lint, classification rules, and match with the raw table
```

`physicalType` is written in PostgreSQL's own spelling, so the test compares it directly with the table. If you change the table, change the contract; the test names the field that differs. The contracts for `listens` and `listened_catalog`, and the test that fails when a restricted field reaches a mart, come in Phase 4.
