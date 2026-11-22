# Contract: the CI workflow

The behavior of `.github/workflows/ci.yml`. The quickstart and `tests/test_quality_gates.py` assert it.

## Triggers and identity

| Item | Value |
| --- | --- |
| Triggers | `pull_request` (opened, synchronize, reopened); `push` to `main` |
| Not used | `pull_request_target` (it would give fork runs write access and secrets) |
| Job id and status name | `checks` (the name to require in branch protection) |
| Runner | `ubuntu-latest` |
| Timeout | 15 minutes |
| Concurrency | one run per pull request; a new push cancels the older run |
| Permissions | `contents: read`, nothing else |

## Steps (in order)

1. Check out the repository with full history (the range scan needs the base commit).
2. Install `uv` (cache enabled).
3. Restore the pre-commit cache.
4. Install `gitleaks` at the pinned version and verify its SHA-256 against the release checksum file; stop if it does not match.
5. Run `make pr-check` with the range of the event: for a pull request, base = the pull request's base commit, head = its head commit; for a push to `main`, base = the commit before the push, head = the pushed commit.

The workflow lists no other check. Adding a check means adding it to `.pre-commit-config.yaml` or to the `pr-check` recipe, and nothing changes in the workflow (SC-007).

## What `make pr-check` does inside the runner

1. `make lint` over all tracked files.
2. `make scan` over the event's range (secrets and IP addresses).
3. Create `.env.ci` with random credentials for `owner`, `dbt` and `agent`, port 55432 and project name `smesh-ci`; register every generated password with the log masker so it never appears in the log.
4. `make up raw-table roles load SOURCE=sample_data` using `ENV_FILE=.env.ci`; wait for the container health check (FR-013).
5. `make test ENV_FILE=.env.ci` with `pytest -rs`; the run fails if any `SKIPPED` line contains `database not reachable` or `role` followed by `cannot connect` (the setup broke and the database tests did not run).
6. Teardown of the `smesh-ci` project and its volume, also when a step failed.

## Guarantees

| Guarantee | How |
| --- | --- |
| No real export or real secret is used | the runner has neither; only `sample_data/` and generated values exist (FR-011) |
| A failure names the failing check | each step and each hook prints its own name; the first failing step ends the job (FR-012) |
| The result does not depend on startup timing | the compose health check gates step 4 (FR-013) |
| Fork pull requests work | no secrets are read; read-only token |
| A local bypass is caught | steps 1 and 2 re-run every check on the whole tree and the pushed commits (SC-006) |
| No skipped database test hides a failure | step 5 parses the `pytest -rs` skip lines and fails on the two reasons above |

## Not in this workflow

`dbt build` (added in Phase 3 as one more line of `pr-check`), the restricted-field test over marts (Phase 4), deploys, notifications outside the pull request status.
