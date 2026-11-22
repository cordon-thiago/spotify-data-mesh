# Implementation Plan: Quality Gates

**Branch**: `004-quality-gates` | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-quality-gates/spec.md`

## Summary

Phase 2b turns the repository's rules into checks that cannot be forgotten. One file, `.pre-commit-config.yaml`, defines the **check set** that runs before every commit on staged files: a path guard (no `data/`, no local settings), a secret and IP-address scan, contract validation, and lint/format for Python, SQL and YAML. A GitHub Actions workflow runs the same set over the whole repository on every pull request and push to `main`, plus a secret and IP-address scan of the commits the change introduces, then starts a throwaway database from the sample data and runs the full test suite. Three `make` targets are the single definition: `make lint` (file checks over all files), `make scan` (secret and IP-address scan over a range of commits) and `make pr-check` (everything the workflow runs); the workflow calls `make pr-check` and lists no check itself. `pr-check` uses its own compose project, port and generated credentials, so it never touches the owner's local database (which holds the real export). Tool choices are recorded in [research.md](research.md) and an ADR (`docs/0002-quality-gates-tooling.md`). One time only, the whole commit history is audited for secrets and IP addresses and the result is recorded in `history-audit.md`.

## Technical Context

**Language/Version**: Python 3.12 (existing); YAML (GitHub Actions, pre-commit); Makefile; SQL (PostgreSQL 16 dialect)

**Primary Dependencies**: New dev dependencies: `pre-commit` 4.7.0, `ruff` 0.17.6, `sqlfluff` 4.5.0, `yamllint` 1.38.0 (the last three are pinned in `.pre-commit-config.yaml` as hook revisions, not as project dependencies). `gitleaks` v8.30.1 (Go binary; managed by pre-commit at commit stage, downloaded with a checksum in CI). Existing: `datacontract-cli`, `pytest`.

**Storage**: PostgreSQL 16 in a throwaway container (compose project `smesh-ci`, volume deleted at the end). No other storage.

**Testing**: Existing `pytest` suite, unchanged, run by `make pr-check` against the throwaway database. New: a small test for the path guard and for the Makefile/workflow single-definition rule (workflow contains no check names), see [contracts/check-set.md](contracts/check-set.md). The existing `tests/test_repo_hygiene.py` stays untouched.

**Target Platform**: Linux / WSL2 for contributors; `ubuntu-latest` GitHub-hosted runner for CI.

**Project Type**: Repository tooling (configuration files, Make targets, one workflow, docs; no service)

**Performance Goals**: Commit stage under 5 s for docs-only and under 30 s for code and contract changes (SC-002, warm cache); workflow under 10 minutes cold (SC-005).

**Constraints**: No real export, no real secret in CI (FR-011). Check output never prints a matched value (FR-003, FR-018): gitleaks runs with `--redact`. `make pr-check` must never reset or write the owner's database (data-safety, see research D9). Fork pull requests get no secrets and the workflow needs none.

**Scale/Scope**: ~70 tracked files, 29 commits, 3 SQL files, 15 Python/YAML sources. Nine hooks, one workflow with one job named `checks`.

**Open items resolved in research.md**: which tool for each check, how the secret scan is split between commit stage and CI range scan, how `pr-check` isolates its database, how the placeholder templater handles psql variables in SQL lint, how existing files reach green, how false positives are allowed narrowly.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Privacy by Permission | PASS | Not weakened. The gates add a second layer (path guard, secret scan) around the same rule; roles and grants stay the enforcement. |
| II. Contracts as Code | PASS | Contract lint runs at commit stage and in CI. The restricted-field-in-marts test stays in Phase 4 (FR-019); the gates can take it as one more step. |
| III. Layered, Tested Transformations | PASS (not applicable) | No dbt yet; Phase 3 adds `dbt build` as one more step of `make pr-check`. |
| IV. Frozen, Reproducible Eval | PASS (not applicable) | |
| V. Reproducible Without Personal Data | PASS | This phase is the enforcement of V and of the constitution workflow rule "before each commit, verify that no file from `data/` or restricted values are staged". CI uses `sample_data/` only and generated credentials; the path guard covers `.claude/settings.local.json` as the constitution requires. |
| VI. Learning-First Phased Delivery | PASS | One concept (automated checks before and after commit). No ✍️ part in the plan, so the assistant writes the configuration. Complexity is bounded: no dependency bots, no coverage, no deploy. This phase is the one deferred from Phase 2. |
| Technology constraints | PASS | English everywhere. No new runtime stack; tooling only. Postgres, ODCS and the Data Contract CLI as before. |
| Quality gates | PASS | The constitution's "change is done only when ... pass" becomes mechanical. A decision record (ADR 0002) is written for the tooling choice, as the constitution asks for significant decisions. |

**Post-design re-check**: unchanged; no violation. Complexity Tracking below is empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-quality-gates/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── check-set.md        # every check: stage, files, fixes in place, failure message
│   └── ci-workflow.md      # triggers, permissions, steps, status name, inputs
├── checklists/requirements.md
├── history-audit.md        # created during implementation (FR-021)
└── tasks.md                # created by /speckit-tasks
```

### Source Code (repository root)

```text
.pre-commit-config.yaml            # the check set (single definition)
.gitleaks.toml                     # secret rules, IPv4 rule, narrow allowances
.sqlfluff                          # SQL lint settings (dialect, placeholder templater)
.yamllint.yaml                     # YAML lint settings
.github/
└── workflows/
    └── ci.yml                     # one job "checks": calls make pr-check
pyproject.toml                     # + [tool.ruff]; + pre-commit in dev group
Makefile                           # + lint, scan, pr-check, hooks targets; ENV_FILE support
.gitignore                         # + .env.ci
docs/
└── 0002-quality-gates-tooling.md  # ADR: tools, alternatives, exit path
README.md                          # + "Quality gates" section (install, commands, bypass, allowances, branch protection)
tests/
└── test_quality_gates.py          # path-guard regex cases; workflow calls only make targets
```

Existing files touched only to bring them to green: the six Python files ruff reformats, any lint findings in Python, SQL and YAML, and the contract formatting if the YAML lint requires it. No behavior change.

**Structure Decision**: Single-project repository tooling at the repository root, as the tools expect (`.pre-commit-config.yaml`, `.github/workflows/`). Settings live in the tool's own file or in `pyproject.toml` for ruff. No new top-level source folder.

## Complexity Tracking

No constitution violations to justify.
