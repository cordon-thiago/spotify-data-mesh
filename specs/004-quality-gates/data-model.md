# Data Model: Quality Gates

This phase has no database objects. The entities of the spec are configuration concepts; this file says where each one lives and which rules it must satisfy.

## Check

One automatic verification of a file type or of repository content.

| Attribute | Meaning | Where it is defined |
| --- | --- | --- |
| `id` | Short name shown in output (for example `ruff-check`) | `.pre-commit-config.yaml` |
| `applies_to` | File types or paths the check runs on (FR-007) | `files:` / `types:` of the hook |
| `stages` | `pre-commit` (staged files) and `all files` (CI and `make lint`) | hook config |
| `fixes_in_place` | Whether it may rewrite files (FR-006) | the tool (`ruff --fix`, `ruff format`, `sqlfluff fix` are not run at commit; only `ruff-format` rewrites) |
| `failure_message` | What the contributor sees; never contains a matched value (FR-003, FR-018) | the tool, plus `--redact` for the scanner |

Rules:

- Every check is listed in exactly one place, `.pre-commit-config.yaml`, except the secret range scan, which is `make scan` (it needs a git range, not a file list).
- A hook with `pass_filenames: true` only sees staged files at commit time and all tracked files under `--all-files`.
- A hook never reads a file under `data/`; the path guard refuses such a file before any content hook looks at it (hooks run in the order of the config).

## Check set

The single list of checks that both stages use.

| Attribute | Meaning | Where |
| --- | --- | --- |
| members | The checks in [contracts/check-set.md](contracts/check-set.md) | `.pre-commit-config.yaml` and `make scan` |
| local commands | `make lint` (file checks), `make scan` (secret and IP scan of a commit range), `make pr-check` (everything the workflow runs) | `Makefile` |
| CI command | `make pr-check` | `.github/workflows/ci.yml` |

Invariant (SC-007): the workflow file names no individual check. Test: `tests/test_quality_gates.py`.

## Workflow

| Attribute | Value | Where |
| --- | --- | --- |
| trigger | `pull_request`, `push` to `main` | `ci.yml` |
| job / status name | `checks` | `ci.yml` |
| permissions | `contents: read` only | `ci.yml` |
| environment | `ubuntu-latest`, no repository secrets, generated database credentials | `ci.yml`, `Makefile` |
| steps | checkout (full history), install uv, install gitleaks, `make pr-check` | `ci.yml` |
| result | pass or fail on the pull request, failing step named by the log | GitHub |

See [contracts/ci-workflow.md](contracts/ci-workflow.md).

## Allowance

A reviewed, narrow exception for a known false positive.

| Attribute | Meaning | Where |
| --- | --- | --- |
| check | The check it applies to | which file holds it |
| scope | One path or one pattern, never "all files" | the file below |
| reason | One line, mandatory | a comment next to the entry |

| Check | File that holds allowances |
| --- | --- |
| Secret and IP scan | `.gitleaks.toml` (`[allowlist]` with a regex and, when needed, a path) |
| Python lint | `pyproject.toml` (`per-file-ignores`) |
| SQL lint | `.sqlfluff` (rule list) or `.sqlfluffignore` (one file, last resort) |
| YAML lint | `.yamllint.yaml` (`ignore:`) |
| Path guard | none: it has no allowances (a file that must be tracked belongs outside the guarded paths) |

Rules: every entry has a reason comment; a reviewer rejects an allowance that covers more than one file or one pattern; the count of allowances is reported by the README checklist and must be zero for the path guard.

## History audit record

| Attribute | Meaning |
| --- | --- |
| date and tool version | when and with what the audit ran |
| commits scanned, refs scanned | counts (SC-010) |
| findings | count, and for each: classification (real or false positive), resolution; no value |
| path check | whether any guarded path was ever tracked, with the count |

Stored in `specs/004-quality-gates/history-audit.md`, created during implementation.
