# Quickstart: Quality Gates

Validation guide for the phase. Contracts: [check-set](contracts/check-set.md), [ci-workflow](contracts/ci-workflow.md). Everything below runs on sample data; nothing prints a field value.

## Prerequisites

- `uv` and Docker reachable from WSL (`docker version` works). For `make scan`, `gitleaks` on PATH (the README says how).
- A clean working tree on branch `004-quality-gates`.

## 1. Install and run the checks

```bash
uv sync
make hooks          # installs the commit hook
make lint           # file checks over the whole repository: expect exit 0
make scan           # secrets and IP addresses in the commits of origin/main..HEAD: expect exit 0
```

Expected: every check from the table passes; no file is changed.

## 2. A commit is refused for a forbidden path (SC-001)

```bash
touch data/streaming_test.json && git add -f data/streaming_test.json
git commit -m "test: should be refused"     # refused, names the file
git reset -q data/streaming_test.json && rm data/streaming_test.json
```

Expected: the commit is refused and no commit is created. The `.env` and `.env.ci` cases are covered by the regex test (`tests/test_quality_gates.py`); never stage the real `.env`. `.env.example` and `data/README.md` are accepted.

## 3. A commit is refused for a secret or an IP address (SC-001)

Create a throwaway file in the scratchpad (not in the repository) that holds a fake key in a known-rule shape, copy it into the repository, stage it and commit.

Do the same with a file that contains an IPv4 address from outside the reserved ranges (a public DNS address is enough; never a real listener address) and with one that contains `203.0.113.9`.

Expected: the secret and the public address are refused; the message gives rule, file and line and does not show the value (it shows `REDACTED`); `203.0.113.9` is accepted. Remove the files afterwards. Never stage the real `.env` for this test: the regex test covers it.

## 4. A broken contract and a style violation are refused (SC-003)

```bash
# remove a required field from the contract, stage, commit -> refused with the validation error
git checkout contracts/spotify_streams.odcs.yaml
# add an unused import to a Python file, stage, commit -> refused (or formatted)
git restore --staged --worktree <the file you changed>   # only the files you changed, never `git checkout .`
```

Expected: both refused with the reason; docs-only commit is accepted (SC-002: under 5 s warm).

## 5. Everything the workflow runs, locally and safely (SC-007)

```bash
make pr-check
```

Expected: lint, range scan, a throwaway database on port 55432 with generated credentials, the full suite with no database skip, teardown. Afterwards `docker compose -p smesh-ci ps` shows nothing, the owner's own database (`make psql`) still holds its rows, and `.env.ci` is ignored by git.

## 6. The workflow on a pull request (SC-004, SC-005, SC-006)

1. Push the branch and open a pull request: status `checks` runs and passes in under 10 minutes.
2. Push a commit with a deliberately failing test: the status turns red and the log names the failing test. Revert.
3. Push a commit made with `git commit --no-verify` that has a lint violation: the status is red on `ruff-check`. Revert.
4. Confirm `.github/workflows/ci.yml` names no individual check (`tests/test_quality_gates.py` also asserts this).

## 7. History audit (SC-010)

```bash
gitleaks git --redact --report-format json --report-path <scratchpad>/audit.json
git log --all --name-only --pretty=format: | sort -u | grep -E '^(data/|\.env$)'
```

Expected: findings (secrets and IP addresses) are zero or each one is classified; the record in `history-audit.md` has counts only. The second command lists only `data/README.md`.

## 8. New contributor (SC-009)

On a fresh clone, follow only the README "Quality gates" section: install hooks, run `make lint`, run `make pr-check`. Expected: under 10 minutes, no step missing.

## Cleanup

`make down` is not needed for `pr-check` (it tears itself down). Remove any file created in steps 2 to 4 (`git status` must be clean).
