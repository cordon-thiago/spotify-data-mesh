# Research: Quality Gates

Versions and dates were read from PyPI and GitHub releases on 2026-11-22. Measurements were made on the current repository with `uvx`, without changing any file.

## D1. Commit-stage runner: pre-commit

- **Decision**: `pre-commit` 4.7.0, added to the `dev` group; hooks installed with `make hooks` (`uv run pre-commit install`).
- **Rationale**: One config file lists every check, runs each only on matching file types (FR-007), isolates tool versions per hook and runs the same config with `run --all-files` for CI (FR-009, FR-015). It is the standard runner for the tools chosen below.
- **Alternatives**: plain `.git/hooks` scripts (not versioned, no per-type filtering); `lefthook` (needs a Go binary, no gain here); `husky` (Node, not used in this repository).

## D2. Python lint and format: ruff

- **Decision**: `ruff` v0.17.6 via `astral-sh/ruff-pre-commit`, rules `E, F, I, UP, B` (errors, pyflakes, import order, modernization, bugbear), `line-length = 120`, settings in `pyproject.toml`.
- **Rationale**: One fast tool replaces flake8, isort and black, and it is the same family as `uv`, already adopted. The repository has no Python lint today.
- **Measurement**: with ruff's broad default rule set, 20 findings (11 auto-fixable) and 10 files to reformat at line length 100; at 120 only 6 files reformat. A narrower explicit rule set removes noise rules (for example `PLW1510` on `subprocess.run`). Remaining findings are fixed in this phase (FR-017).
- **Alternatives**: flake8 + black + isort (three tools, three configs); pylint (slow, noisy for this size).

## D3. SQL lint: sqlfluff

- **Decision**: `sqlfluff` 4.5.0, dialect `postgres`, `max_line_length = 120`, only on `sql/**/*.sql`; `.sqlfluff` at the root.
- **Rationale**: Only SQL linter with a PostgreSQL dialect and fix mode. FR-005 asks for SQL lint.
- **Measurement and risk**: `sql/roles.sql` contains psql variables (`:'dbt_password'`), which the parser cannot read ("unparsable section"). With the `placeholder` templater and `param_style = colon_optional_quotes` it parses and only style findings remain (long lines, keyword newline, identifier case). Fix: configure the templater and run `sqlfluff fix`; review the diff, since this file is privacy-critical and tests (`test_roles_db.py`) must still pass. **Fallback** if a construct still does not parse: list that one file in `.sqlfluffignore` with the reason, as a narrow allowance (FR-017).
- **Alternatives**: `sqlfmt` (no PostgreSQL DO-block and psql-variable support, formatting only); `pgFormatter` (formatter, no lint); no SQL lint (rejected: FR-005).

## D4. YAML lint: yamllint

- **Decision**: `yamllint` v1.38.0, `.yamllint.yaml` with `line-length: 120` and `document-start: disable`; applied only to `contracts/`, `docker-compose.yml`, `.github/`, `.pre-commit-config.yaml` (and `dbt/` when it exists in Phase 3). `.specify/` and `.claude/` are tool-managed and excluded.
- **Rationale**: Contracts, the container definition and the workflow are YAML that the project edits by hand; syntax and style errors there are the likely ones. `.env.example` is not YAML and is not matched.
- **Measurement**: default settings flag every long line, but the existing files are otherwise clean; the relaxed config should leave zero findings.
- **Alternatives**: `check-yaml` from `pre-commit-hooks` (syntax only, no style); `actionlint` for the workflow (good, but a seventh tool; revisit if the workflow grows).

## D5. Contract validation: existing command

- **Decision**: a `local` hook that runs `uv run datacontract lint` on staged `contracts/*.odcs.yaml` (the same command as the existing `make lint-contract`).
- **Rationale**: FR-004 asks to validate staged contracts; the command exists from Phase 2 and is not redefined (Assumptions).
- **Alternatives**: calling the Data Contract CLI with a pre-commit hook from its repository (no official hook).

## D6. Path guard: a hook that always fails on forbidden paths

- **Decision**: a `local` hook with `language: fail` and a `files:` regex that matches the raw-data folder except its guide, the local settings files (`.env`, `.env.ci`), `.claude/settings.local.json`, and `*.pem`/`*.key`. The hook fails whenever a staged file matches, whatever its content.
- **Rationale**: FR-002 and the constitution's workflow rule. It holds even for `git add -f` past the ignore rule (Edge Cases). It needs no scanner and prints only file names.
- **Regex shape**: `^(data/(?!README\.md$)|\.env$|\.env\.ci$|\.claude/settings\.local\.json$)`; `.env.example` does not match.
- **Alternatives**: rely on `.gitignore` (bypassed by `-f`); `check-added-large-files` (does not know about personal data).

## D7. Secret scan: gitleaks, split in two uses

- **Decision**: `gitleaks` v8.30.1.
  - **Commit stage**: the official `gitleaks/gitleaks` pre-commit hook scanning staged changes, with `--redact` so a matched value is never printed (FR-003).
  - **CI and audit**: `gitleaks git --redact --log-opts="<base>..<head>"` over the commits a pull request (or push to `main`) introduces (FR-022); the one-time audit runs `gitleaks git --redact` over all history (FR-021). Both go through `make scan`.
- **Rationale**: ruff cannot scan secrets and the plan said so (the path guard is not a scanner). gitleaks is the most used open-source scanner, has rules for credentials and keys, supports a narrow allowlist file, and has a range mode. The existing IP-address test (`test_repo_hygiene.py`) remains: it finds personal data (addresses), gitleaks finds credentials, so they do not overlap.
- **Binary**: pre-commit builds and caches the hook's binary; CI downloads the pinned release and verifies its SHA-256 from the release's checksum file. `make scan` fails with an install message if the binary is missing (Edge Cases). Verified SHA-256 of `gitleaks_8.30.1_linux_x64.tar.gz` (checked against the release checksum file on 2026-11-22): `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`; the workflow pins this value.
- **Allowances**: `.gitleaks.toml` extends the default rules and allows one reviewed pattern: the placeholder `change_me_local_only` in `.env.example` and docs, by regex and by path. No global switch.
- **IP rule (FR-024)**: a custom rule `ip-address` in `.gitleaks.toml` with an RE2-compatible regex (no lookaround) `\b(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b` and a rule allowlist for the reserved ranges (192.0.2., 198.51.100., 203.0.113., 127., 0.0.0.0), the same set as `tests/test_repo_hygiene.py`. It closes a gap with the constitution ("before each commit, verify that no ... restricted field values are staged"): the hygiene test only runs after the commit. It also makes the one-time history audit look for IP addresses, which the hygiene test never did (it scans the working tree). Expected false positives are four-part version numbers; each gets a narrow allowance with a reason. IPv6 is left to the hygiene test because a candidate regex for it is too noisy for a pre-commit hook.
- **Alternatives**: `detect-secrets` (last release 2024-05, needs a baseline file to maintain); `trufflehog` (heavier, built for history scans); GitHub's own secret scanning (alerts after push, not before commit; useful as an extra, not a gate).

## D8. CI platform and workflow shape

- **Decision**: GitHub Actions, `.github/workflows/ci.yml`, one job named `checks` on `ubuntu-latest`, triggers `pull_request` and `push` to `main`, `permissions: contents: read`, `concurrency` cancelling older runs of the same pull request, `timeout-minutes: 15`. Steps: checkout with full history (needed by the range scan), `astral-sh/setup-uv` (cache on), install gitleaks (pinned, checksum-verified), `make pr-check BASE=<base sha> HEAD=<head sha>`.
- **Rationale**: The repository is on GitHub, and a runner has Docker, so the same `docker-compose.yml` runs there. One job keeps the status name stable for branch protection (name `checks`). Using `pull_request` (not `pull_request_target`) gives fork runs no secrets.
- **Pinning**: third-party actions are pinned to a full commit SHA with the version in a comment, resolved at implementation (`actions/checkout` v7.0.1, `astral-sh/setup-uv` v10.4.0 were the latest on 2026-11-22).
- **Alternatives**: separate jobs for lint and tests (faster feedback, but two status names and the database startup would be duplicated for no gain at this size); `gitleaks-action` (adds a license requirement for organizations and a second path to the same check; the binary through `make scan` keeps one definition).

## D9. One definition and a safe `pr-check`

- **Decision**: `make lint` = `pre-commit run --all-files`; `make scan BASE=<ref> HEAD=<ref>` = gitleaks range scan (default `origin/main..HEAD`); `make pr-check` = `lint` + `scan` + throwaway database + `pytest` + teardown. The workflow runs only `make pr-check`. A test asserts that the workflow file lists no individual check (SC-007).
- **Data safety**: the owner's local database holds the real export (7,922 rows). `make pr-check` therefore never calls `make reset`. It generates `.env.ci` (git-ignored) with random credentials, port 55432 and `COMPOSE_PROJECT_NAME=smesh-ci`, runs `make up raw-table roles load SOURCE=sample_data` and `make test` with `ENV_FILE=.env.ci`, and removes the `smesh-ci` project and volume at the end, also on failure. A separate project name gives a separate volume, so the owner's `pgdata` is never mounted.
- **Why a file and not variables**: the Makefile does `-include .env`, and the tests read the environment first and then `.env`; a generated env file selected with `ENV_FILE` is read the same way by every nested `make` and by pytest, whereas command-line variables do not reliably reach the `make roles` call that `tests/test_roles_db.py` runs.
- **Alternatives**: reuse the owner's database in CI-like mode (rejected: risk to real data); a service container in the workflow only (rejected: the local command would differ from the workflow, breaking FR-015).

## D10. Existing files reach green

- **Decision**: in this phase run `ruff check --fix` and `ruff format`, `sqlfluff fix` on `sql/`, and fix the remaining findings by hand; review every diff and run `make test` against a local database before committing. Gate order: add the config, fix the files, then enable the hooks, so the first run is green (FR-017, SC-008).
- **Risk**: reformatting `tests/test_roles_db.py` and `sql/roles.sql` must not change behavior; the permission tests are the guard.

## D11. One-time history audit (FR-021)

- **Decision**: run `gitleaks git --redact` over all refs once (secret rules plus the `ip-address` rule), and a path check over history (`git log --all --name-only` against the path guard regex). Record counts and results in `history-audit.md`, never values.
- **Preliminary result (path check, read-only)**: 29 commits across all refs; the only path ever tracked under the forbidden set is `data/README.md`. No `.env` and no `.claude/settings.local.json` in history. The gitleaks scan itself is a task of the implementation.
- **If a finding is real**: rotate the credential and, if needed, rewrite history before the phase ends (SC-010). The repository is public, so this is not optional.

## D12. Documentation and decision record

- **Decision**: README "Quality gates" section (install hooks, the two commands, how to allow a reviewed false positive, that bypassing with `--no-verify` is caught by CI, recommended branch protection with required check `checks`) and `docs/0002-quality-gates-tooling.md` with the tools above, alternatives and exit path (FR-016, FR-020).
- **Branch protection**: stays an owner decision and a repository setting (Assumptions). The README states the recommended ruleset; enabling the required check comes after the workflow has run once.

## D13. Cost and speed

- **Decision**: cache the pre-commit environments (`~/.cache/pre-commit`) and `uv` in CI. The first cold run installs hook environments (about a minute), later runs reuse them.
- **Rationale**: keeps SC-005 (under 10 minutes) with a wide margin and SC-002 realistic for commits.
