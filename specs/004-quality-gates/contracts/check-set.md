# Contract: the check set

What each check does, which files it sees, and how it fails. The tests and the quickstart assert this table. Order is the order of `.pre-commit-config.yaml` (cheap and most important first).

| # | Check id | Tool (version) | Applies to | Commit stage | `make lint` | Fixes in place | Spec |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `path-guard` | pre-commit `language: fail` | staged paths matching the forbidden regex | yes | yes | no | FR-002 |
| 2 | `gitleaks` | gitleaks v8.30.1, `--redact`, secret rules plus rule `ip-address` | staged changes (commit stage) | yes | no (see `make scan`) | no | FR-003, FR-024 |
| 3 | `check-merge-conflict` | pre-commit-hooks v6.0.0 | all text files | yes | yes | no | FR-001 |
| 4 | `check-added-large-files` | pre-commit-hooks v6.0.0, limit 500 KB | added files | yes | yes | no | FR-002 (a safety net for a data file with another name) |
| 5 | `ruff-check` | ruff v0.17.6 | `*.py` | yes | yes | no (report only) | FR-005 |
| 6 | `ruff-format` | ruff v0.17.6 | `*.py` | yes | yes (rewrites the file, then fails if it changed) | yes (formatting) | FR-005, FR-006 |
| 7 | `sqlfluff-lint` | sqlfluff 4.5.0 | `sql/**/*.sql` | yes | yes | no | FR-005 |
| 8 | `yamllint` | yamllint v1.38.0 | `contracts/`, `docker-compose.yml`, `.github/`, `.pre-commit-config.yaml` | yes | yes | no | FR-005 |
| 9 | `contract-lint` | `uv run datacontract lint` | `contracts/*.odcs.yaml` | yes | yes | no | FR-004 |

`make scan` (not a hook): `gitleaks git --redact --log-opts="BASE..HEAD"`, with the same secret rules and the `ip-address` rule. Default range `origin/main..HEAD`; the workflow passes the pull request's base and head. This is the check of FR-022; the one-time audit (FR-021) runs it without a range.

## Forbidden paths (check 1)

Regex (matches a repository-relative path):

```text
^(data/(?!README\.md$)|\.env$|\.env\.ci$|\.claude/settings\.local\.json$|.*\.(pem|key)$)
```

| Path | Expected |
| --- | --- |
| `data/streaming_history_0.json` | refused |
| `data/README.md` | accepted |
| `.env` | refused |
| `.env.ci` | refused |
| `.env.example` | accepted |
| `.claude/settings.local.json` | refused |
| `sample_data/streaming_history_audio_sample.json` | accepted |
| `server.key` | refused |

`tests/test_quality_gates.py` runs these rows against the regex read from `.pre-commit-config.yaml`, so the table and the config cannot drift.

## IP rule (check 2, FR-024)

| Text | Expected |
| --- | --- |
| an IPv4 address from outside the reserved ranges (for example a public DNS address) | refused, message gives file and line, shows `REDACTED` |
| `203.0.113.9`, `198.51.100.7`, `192.0.2.1`, `127.0.0.1`, `0.0.0.0` | accepted |
| a four-part version number | allowed only through a narrow allowance with a reason |
| an IPv6 address | not checked here; `tests/test_repo_hygiene.py` covers it |

## Failure messages

| Check | A failure shows | A failure never shows |
| --- | --- | --- |
| `path-guard` | the file name and "forbidden path" | file content |
| `gitleaks` | rule id, file, line, commit (range scan) | the matched value (`--redact`) |
| `contract-lint` | the Data Contract CLI validation error | field values |
| `ruff-*`, `sqlfluff-lint`, `yamllint` | rule id, file, line | nothing sensitive is in their output beyond source lines of the repository itself |

Source lines in lint output come from tracked repository files, not from `data/`; the path guard stops a `data/` file before it can reach them, and `make lint` only reads tracked files.

## Commands

| Command | Does | Needs |
| --- | --- | --- |
| `make hooks` | `uv run pre-commit install` (commit hook) | `uv` |
| `make lint` | `pre-commit run --all-files` without the secret hook (checks 1, 3 to 9) | `uv` (a clear message and exit 2 if `uv` or the synced environment is missing) |
| `make scan [BASE= HEAD=]` | gitleaks range scan: secrets and IP addresses | `gitleaks` on PATH, else prints how to install it and exits 2 |
| `make pr-check` | `lint`, `scan`, throwaway database, full `pytest`, teardown | Docker reachable, `gitleaks`, `uv` |

Exit codes: 0 all passed; 1 a check failed; 2 a prerequisite is missing (`uv`, the synced environment, `gitleaks` or Docker: a clear one-line message that says what to install, no stack trace).
