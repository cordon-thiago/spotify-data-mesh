# Quality gates

Automatic checks run before every commit and again on every pull request, so the rules of this repository do not depend on remembering them. They protect the one thing that cannot be undone in a public repository: personal data and secrets reaching git. Tool choices and alternatives: [ADR 0002](../adr/0002-quality-gates-tooling.md).

Three layers keep personal data out: a commit that stages a forbidden path, a secret or an IP address is refused; every pull request is checked again in CI; and `make test` checks that `data/` is ignored and that no tracked file contains an IPv4 or IPv6 address outside the reserved documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `2001:db8::/32`). The one-time audit of the whole git history is in [specs/004-quality-gates/history-audit.md](../../specs/004-quality-gates/history-audit.md); the hygiene test reads the working tree only.

## One-time install

```bash
uv sync                # includes pre-commit
make hooks             # installs the git pre-commit hook
```

For `make scan` and `make pr-check`, also install [gitleaks](https://github.com/gitleaks/gitleaks/releases) v8.30.1: download `gitleaks_8.30.1_linux_x64.tar.gz` and the release's checksum file, check it with `sha256sum -c --ignore-missing`, and put the `gitleaks` binary on your `PATH` (for example `~/.local/bin`). The CI workflow pins the same version and checksum.

## What runs before each commit

Staged files only; a docs-only commit takes well under a second.

| Check | Refuses |
| --- | --- |
| `path-guard` | A staged file from `data/` (except its guide), `.env`, `.env.ci`, `.claude/settings.local.json` or a key file, even when added with `git add -f` |
| `gitleaks` | A secret or an IPv4 address outside the reserved ranges; the message gives file and line and never prints the value |
| `check-merge-conflict`, `check-added-large-files` | Conflict markers; files over 500 KB |
| `ruff-check`, `ruff-format` | Python lint errors; unformatted Python (the formatter rewrites the file, stage it and commit again) |
| `sqlfluff-lint` | SQL lint errors in `sql/` |
| `yamllint` | YAML errors in contracts, `docker-compose.yml` and the workflow |
| `contract-lint` | An invalid data contract (Data Contract CLI) |

The commit stage does not run the test suite and does not need the database.

## The three commands

| Command | Does | Needs |
| --- | --- | --- |
| `make lint` | The file checks above over all tracked files | `uv` |
| `make scan [BASE= HEAD=]` | Secrets and IP addresses in the commits of a range (default `origin/main..HEAD`) | `gitleaks` |
| `make pr-check [BASE= HEAD=]` | Everything the CI workflow runs: `lint`, `scan`, then a throwaway database from the sample data and the full test suite | Docker, `gitleaks`, `uv` |

`make pr-check` uses its own database (compose project `smesh-ci`, port 55432, generated credentials in `.env.ci`) and removes it afterwards. It never touches your own database or its data.

## In CI

`.github/workflows/ci.yml` has one job, `checks`, on every pull request and on every push to `main`. It installs the tools and runs `make pr-check`; it lists no check itself, so the local commands and CI cannot drift apart. It uses a read-only token and no secret, and a skipped database test counts as a failure. `git commit --no-verify` skips the local stage, and CI catches the same problem.

## Allowing a reviewed false positive

One narrow entry, with a reason written next to it, in the file of the check that complained:

| Check | File |
| --- | --- |
| Secret and IP scan | `.gitleaks.toml` (`[[allowlists]]` or the allowlist of the rule) |
| Python lint | `pyproject.toml` (`[tool.ruff.lint.per-file-ignores]`) |
| SQL lint | `.sqlfluff` (rule list), or `.sqlfluffignore` for one file as a last resort |
| YAML lint | `.yamllint.yaml` (`ignore:`) |
| Path guard | none: a file that must be tracked belongs outside the guarded paths |

## Recommended branch protection

A repository setting; enabling it is the owner's decision: a ruleset on `main` that requires a pull request, requires the status check `checks` (after the workflow has run once, so GitHub lists it), blocks force pushes and blocks deletion.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `error: uv is required` or `error: run uv sync first` | A quality-gate target cannot find the tool | Install [uv](https://docs.astral.sh/uv/), then `uv sync` |
| `error: gitleaks is required` | `make scan` or `make pr-check` cannot find the scanner | Install gitleaks v8.30.1 (see One-time install) |
| A commit is refused | The hook names the check, the file and the line | Fix it, or add one reasoned allowance (see above) |
