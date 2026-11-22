# ADR 0002: Quality gates with pre-commit, gitleaks, ruff, sqlfluff and GitHub Actions

- **Status**: Accepted
- **Date**: 2026-11-22
- **Deciders**: Project owner

## Context

The repository is public and the real Spotify export holds personal data (an IP address and a detailed listening record). The constitution says "before each commit, verify that no file from `data/` or restricted field values are staged" and "secrets MUST NOT be committed". Until Phase 2 that depended on remembering to run `make test` before a push, and the hygiene test reads the working tree, not git history.

Phase 2b makes these rules automatic: checks before each commit, and the same checks again on every pull request, which cannot be skipped. Details: [specs/004-quality-gates/](../../specs/004-quality-gates/).

## Decision

| Need | Tool (version) | How it is used |
| --- | --- | --- |
| Run checks before a commit | pre-commit 4.7.0 | `.pre-commit-config.yaml` is the single definition; `make hooks` installs it |
| Forbidden paths | pre-commit `language: fail` hook | A regex on staged paths; no scanner, refuses even `git add -f` |
| Secrets and IP addresses | gitleaks v8.30.1, `--redact` | Staged changes at commit, commit ranges through `make scan`, one-time audit of the history; rules and allowances in `.gitleaks.toml` |
| Python | ruff v0.17.6 | Lint (`E,F,I,UP,B`) and format, line length 120, settings in `pyproject.toml` |
| SQL | sqlfluff 4.5.0 | PostgreSQL dialect; the `placeholder` templater reads the psql variables in `sql/roles.sql` |
| YAML | yamllint v1.38.0 | Contracts, `docker-compose.yml`, the workflow |
| Contracts | Data Contract CLI (existing) | `datacontract lint` on staged contracts |
| CI | GitHub Actions | One job `checks`; it installs the tools and runs `make pr-check`, and lists no check itself |

Three Make targets are the one definition of "the checks": `make lint` (file checks), `make scan` (secrets and IP addresses over a commit range) and `make pr-check` (everything the workflow runs, on a throwaway database that never touches the owner's data).

## Alternatives considered

| Option | Why not chosen |
| --- | --- |
| Plain git hooks | Not versioned, no per-file-type filtering |
| `detect-secrets` | Last release in 2024, needs a baseline file to maintain |
| `trufflehog` | Built for history scans; heavy for a pre-commit hook |
| `gitleaks-action` | A second path to the same check and a licence rule for organizations; the pinned binary through `make scan` keeps one definition |
| flake8 + black + isort | Three tools and three configs for what ruff does alone |
| `sqlfmt` or `pgFormatter` | No PostgreSQL lint, or no support for psql variables |
| Separate CI jobs for lint and tests | Two status names and the database set up twice, for no gain at this size |
| GitHub secret scanning only | Alerts after the push, not before the commit; useful as an extra, not as the gate |

## Consequences

- A commit takes about a second with warm hook environments (0.4 s for docs only, 1.2 s for code and a contract, measured on 2026-11-22). `make pr-check` took 20 s locally. The `checks` job on GitHub took 55 s on the first pull request (target: under 10 minutes).
- Hook versions are pinned in `.pre-commit-config.yaml`; upgrades are deliberate (`pre-commit autoupdate`, then review).
- The IP rule matches any valid IPv4 address outside the reserved documentation ranges, so a four-part version number would be a false positive; it would get a narrow, reasoned allowance. IPv6 stays covered only by `tests/test_repo_hygiene.py`, on the working tree.
- `sqlfluff` rule LT01 (spacing) is off, so the aligned column definitions in `sql/raw_spotify_streams.sql` stay readable. Line length is 130 for SQL because of one long string literal.
- Existing files were brought to pass in this phase: formatting in 9 Python files, layout in `sql/roles.sql`, and long descriptions in the contract wrapped without changing their text. `raise ... from None` was added in `ingest/load.py` so a chained database error can never reach the output.
- `make pr-check` uses its own compose project (`smesh-ci`), port 55432 and generated credentials, so it is safe to run next to the owner's database.
- Branch protection (a ruleset requiring the `checks` status) is a repository setting and the owner's decision; the README describes the recommended ruleset.
- The privacy test over the marts (Phase 4) and `dbt build` (Phase 3) are added later as one more line of `make pr-check`.

## Exit path

- Replace a check: edit its hook in `.pre-commit-config.yaml`; nothing else changes.
- Replace GitHub Actions: any CI service only has to install `uv` and gitleaks and run `make pr-check`.
- Drop the commit stage: remove `make hooks`; CI still runs every check.

## Review trigger

Re-evaluate at the start of Phase 3 (dbt joins the check set), at Phase 4 (privacy test over the marts) and whenever the IP rule or a tool upgrade produces recurring false positives.
