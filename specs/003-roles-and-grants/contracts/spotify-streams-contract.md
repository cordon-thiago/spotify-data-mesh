# Contract: the spotify_streams data contract file

Rules `contracts/spotify_streams.odcs.yaml` must satisfy and `tests/test_contract.py` must check. Satisfies FR-012 to FR-017.

## Interface

| Item | Value |
| --- | --- |
| File | `contracts/spotify_streams.odcs.yaml` |
| Lint | `make lint-contract` (Data Contract CLI `lint`), exit code 0 |
| Drift test | `tests/test_contract.py`, reads the live raw table, skipped when the database is unreachable |

## Rules

| # | Rule | Test |
| --- | --- | --- |
| 1 | The file passes the Data Contract CLI lint | run the CLI, exit code 0 |
| 2 | Property names equal the table's column names, no extras either way | set difference; failure names the field |
| 3 | Each `physicalType` equals the table's `information_schema` `data_type` | per field; failure names the field |
| 4 | Every property has a non-empty `description` | parse |
| 5 | Every property has exactly one `classification` in `restricted`, `confidential`, `internal` | parse |
| 6 | Exactly one property is `restricted`, and it is `ip_addr`; `conn_country` is `confidential` | parse |
| 7 | The `roles` section gives access to `owner` and `dbt` only; the description states that `agent` has none | parse |
| 8 | The description states that a future user agent or username field is restricted by default | text match |
| 9 | The four nullable booleans state that `null` means unknown | text match on the four properties |
| 10 | No data value from the export appears in the file | covered by the repo hygiene test |

## Known limit

A restricted field mislabeled as internal is not detected here. Detecting a restricted field inside a mart is the Phase 4 test.
