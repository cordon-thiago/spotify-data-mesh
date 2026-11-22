# History audit (FR-021, SC-010)

One-time audit of the whole commit history for secrets, IPv4 addresses outside the reserved ranges, and files from guarded paths. Counts and classifications only: no matched value appears in this file.

| Item | Result |
| --- | --- |
| Date | 2026-11-22 |
| Tool | gitleaks 8.30.1, config `.gitleaks.toml` (default rules plus rule `ip-address`), `--redact` |
| Scope | all refs of the repository (10 refs: 6 local branches, 4 remote branches) |
| Commits in the repository | 32 (`git rev-list --all`) |
| Commits scanned | 29 (the commits that carry a diff; the 3 merge commits carry none of their own) |
| Final findings | **0** (secrets: 0, IP addresses: 0) |
| Unresolved real findings | **0** |

## Path check

Command: list every path ever tracked in any ref and match it against the path-guard set (`data/` except its guide, `.env`, `.env.ci`, `.claude/settings.local.json`, `*.pem`, `*.key`).

| Result | Count |
| --- | --- |
| Paths ever tracked that match the set | 1: `data/README.md`, the one file the guard allows |
| `.env`, `.env.ci`, `.claude/settings.local.json`, key files in history | 0 |

## First run and how it was resolved

The first scan used the rule `ip-address` with a generic four-numbers pattern and reported 6 findings, in 3 files (`specs/001-local-dev-foundation/research.md`, `specs/001-local-dev-foundation/tasks.md`, `tests/test_repo_hygiene.py`) at 3 commits. Classification of each, done without printing values:

| Finding | Classification | Why |
| --- | --- | --- |
| 6 of 6 | false positive | Each line holds the documented mask `00.000.000.000` (the text the hygiene test allows). It is not an address: it has leading zeros. The other four-part numbers on those lines are reserved documentation addresses, which the rule already allowed. No valid public address was among them. |

Resolution: the rule's regex was tightened to valid octets (0 to 255, no leading zero), so the mask is no longer read as an address. No allowance entry was needed. After the change the scan reports 0 findings. A four-part version number would still match; the repository has none, and one would get a narrow allowance with a reason.

## What this does not cover

- IPv6 addresses: covered only by `tests/test_repo_hygiene.py`, on the working tree (not on history).
- Content of deleted untracked files and of the local `data/` folder: never committed, not scanned (the audit reads commits only).
- Anything pushed after this date: covered by the pull-request range scan (`make scan`, FR-022).
