# Feature Specification: Quality Gates

**Feature Branch**: `004-quality-gates`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "Phase 2b: Quality gates (concept: automated checks before and after commit). Pre-commit hooks and a CI workflow so that checks run the same locally and on every PR. Scope as defined in .claude/plans/implementation-plan.md section 'Phase 2b'. Tool choices are left to the plan step."

## Clarifications

### Session 2026-11-22

- Q: In CI, should the secret scan cover the whole history, only the pull request's commits, or the history once now and then only each pull request's commits? → A: One audit of the whole history in this phase, then only the commits of each pull request (and of each change to the main branch).
- Q: Should the full test suite (which needs the database) also run before each commit? → A: No. The commit stage runs only fast checks; the full test suite runs in the workflow and on demand through the local pull-request command.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A commit that would leak personal data or a secret is blocked (Priority: P1)

The project owner (or any contributor) tries to commit. Before the commit is created, an automatic check looks at what is staged. If the staging area contains a file from the raw-data folder, a local settings file with real values, or content that looks like a secret, the commit is refused with a message that names the file and the reason. Nothing is written to history.

**Why this priority**: The repository is public and the raw export is personal data (Principle V and the constitution's workflow rule "before each commit, verify that no file from `data/` or restricted field values are staged"). Today that rule depends on the owner remembering it. This story turns it into a guarantee, and it is the one failure that cannot be undone once pushed.

**Independent Test**: Stage a file under the raw-data folder, then try to commit: refused. Unstage it, stage the local settings file, try again: refused. Unstage it, stage a file containing a fake credential pattern: refused. Stage an ordinary documentation change: accepted.

**Acceptance Scenarios**:

1. **Given** the checks are installed, **When** a file inside the raw-data folder is staged (even by forcing past the ignore rule) and a commit is attempted, **Then** the commit is refused and the message names the file.
2. **Given** the checks are installed, **When** the local settings file (the one holding real passwords) is staged, **Then** the commit is refused.
3. **Given** the checks are installed, **When** a staged file contains a value that looks like a password, key or token, **Then** the commit is refused and the message names the file and line, without printing the value.
4. **Given** the checks are installed, **When** only ordinary, clean files are staged, **Then** the commit is accepted without noticeable delay.
5. **Given** the example settings file lists placeholder values, **When** it is staged, **Then** it is accepted; placeholders are not secrets.
6. **Given** the checks are installed, **When** a staged file contains an IPv4 address outside the reserved ranges, **Then** the commit is refused and the message names the file and line without printing the address; an address inside the reserved documentation ranges is accepted.

---

### User Story 2 - A broken contract or badly formatted file is blocked before commit (Priority: P2)

When a commit includes a data contract, a Python file, a SQL file or a configuration file, the matching checks run on those files only. An invalid contract, a style violation or a malformed file stops the commit with a message that says what to fix. Simple violations that can be fixed mechanically (formatting) are fixed in place, so the contributor only has to stage the result and commit again.

**Why this priority**: Contracts are code (Principle II). Catching an invalid contract at commit time is far cheaper than finding it in a later phase. It is lower than Story 1 because a style slip is recoverable and a leak is not.

**Independent Test**: Break the contract (remove a required field), stage it and commit: refused, with the reason. Fix it and commit: accepted. Stage a Python file with a style violation: refused or auto-fixed. Stage a SQL file and a YAML file with violations: refused.

**Acceptance Scenarios**:

1. **Given** the checks are installed, **When** a staged contract is invalid, **Then** the commit is refused and the validation error is shown.
2. **Given** the checks are installed, **When** a staged Python file has a lint or format violation, **Then** the commit is refused, or the file is fixed in place when the violation is mechanical, and the contributor is told which.
3. **Given** the checks are installed, **When** a staged SQL file or configuration file is malformed or breaks the project's style rules, **Then** the commit is refused with the location of the problem.
4. **Given** the staged files are valid, **When** the commit is made, **Then** only the checks that match the staged file types run, so a documentation-only commit does not wait for the contract or code checks.

---

### User Story 3 - Every pull request runs the same checks, and a failure is visible (Priority: P2)

When a pull request is opened or updated, and when a change reaches the main branch, an automatic workflow runs the same checks as the commit stage on the whole repository, then builds a clean database from the sample data, applies the SQL setup and runs the test suite. The result appears as a pass or fail status on the pull request. A failing test turns the status red and says which check failed.

**Why this priority**: Local checks can be skipped (a commit can bypass them on purpose or by accident, and a contributor may never install them). The pull request check is the one that cannot be skipped, and it is what makes "Definition of done" in the constitution true for every merge.

**Independent Test**: Open a pull request with a deliberately failing test: the status is red and names the test. Fix it: green. Open one with a bypassed local check that has a style violation: the workflow still fails on it.

**Acceptance Scenarios**:

1. **Given** a pull request, **When** it is opened or updated, **Then** the workflow runs the commit-stage checks over the whole repository and the full test suite on a database built from sample data.
2. **Given** a pull request with a failing test, **When** the workflow finishes, **Then** the status is failed and the failing check is named in the result.
3. **Given** a pull request that bypassed the local checks, **When** the workflow runs, **Then** the same violation is caught there.
4. **Given** a change that reaches the main branch, **When** the workflow runs, **Then** it runs the same checks, so the main branch has a known state.
5. **Given** the workflow runs in a clean environment with no real export and no real passwords, **When** it runs, **Then** it passes using only the sample data and throwaway credentials created for the run.

---

### User Story 4 - Local and CI checks cannot drift apart (Priority: P3)

A contributor can run, with one command, exactly the file checks the commit stage runs over all files, with a second command the secret and IP-address scan over a range of commits, and with a third command exactly what the pull request workflow runs. The workflow itself calls those same commands instead of repeating the check list.

**Why this priority**: Two separate lists of checks always diverge, and the contributor learns about it from a red status after pushing. One source of truth keeps the feedback loop short. It is not first because Stories 1 to 3 deliver value even if the lists are maintained twice.

**Independent Test**: Run the local "all checks" command on a clean checkout and compare its list of checks with the one in the workflow: they are the same. Add a new check in one place and observe it run in both.

**Acceptance Scenarios**:

1. **Given** a clean checkout, **When** the contributor runs the file-checks command, **Then** every file check runs over all tracked files and the result is pass or fail.
2. **Given** a clean checkout and Docker available, **When** the contributor runs the pull-request command, **Then** the same steps as the workflow run, in the same order.
3. **Given** the workflow definition, **When** it is read, **Then** each step calls one of those commands and does not list the individual checks again.
4. **Given** a new contributor, **When** they follow the repository guide, **Then** they can install the commit-stage checks with one documented command.

---

### Edge Cases

- A contributor bypasses the local checks on purpose: the pull request workflow must catch the same problem; bypassing the local stage never lets a violation reach the main branch unnoticed.
- A raw-data file is force-added past the ignore rule: the commit-stage path check must still refuse it, because the ignore rule alone does not protect against it.
- A secret check flags a harmless placeholder (the example settings file, fake credentials in tests, documentation-range IP addresses used in fixtures): the project must have a documented, reviewed way to allow a specific false positive, and the allowance must be narrow (one file or one pattern, not a switch that turns the check off).
- A secret check finds a real-looking value: the message must name the file and line but never print the value, so the message itself cannot leak it.
- The workflow needs a database and passwords: it must create throwaway ones for the run and never read a real secret, so a pull request from a fork cannot reach anything private.
- The workflow is slow or the database is slow to start: the workflow must wait until the database is ready before applying setup, so it does not fail intermittently.
- The checks themselves need a tool that is not installed locally: the all-checks command must fail with a clear message on how to install it, not with a confusing error.
- The first run on the existing repository finds many old violations: existing files must be brought to pass in this phase (or explicitly listed as allowed), so the gates start green and stay meaningful.
- The commit-stage checks and the existing hygiene test overlap (both look for personal data): the plan step decides how to avoid duplication, and neither may be weakened.
- Text that looks like an IP address but is not one (a four-part version number): the IP rule allows the reserved ranges, and any other false positive goes through a narrow, reasoned allowance, never through a switch that turns the rule off.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Before each commit, the repository MUST run automatic checks over the staged files, and MUST refuse the commit when any check fails.
- **FR-002**: The commit-stage checks MUST refuse any staged file inside the raw-data folder (except its tracked guide file) and the local settings file that holds real values, even when the file was force-added past the ignore rule.
- **FR-003**: The commit-stage checks MUST scan staged content for secret-like values (passwords, keys, tokens) and refuse the commit when one is found. The message MUST give file and line and MUST NOT print the matched value.
- **FR-004**: The commit-stage checks MUST validate every staged data contract and refuse the commit when validation fails.
- **FR-005**: The commit-stage checks MUST lint and format-check staged Python files, lint staged SQL files, and check the syntax and style of staged configuration files (contracts, container definition, workflow definition).
- **FR-006**: Mechanical fixes (formatting) MAY be applied in place; any such fix MUST still require the contributor to stage the result and commit again, so no change enters history unreviewed.
- **FR-007**: Each commit-stage check MUST run only on the file types it applies to, so a commit touching only documentation does not run the contract or code checks.
- **FR-008**: The repository MUST contain a continuous-integration workflow that runs on every pull request and on every change that reaches the main branch.
- **FR-009**: The workflow MUST run the commit-stage checks over the whole repository, not only over changed files.
- **FR-010**: The workflow MUST then start a database in a clean state, load the synthetic sample data, apply the SQL setup (table, layers, roles and grants), and run the full test suite against it.
- **FR-011**: The workflow MUST NOT use the real export or any real secret. It MUST use only the sample data and throwaway credentials generated for that run.
- **FR-012**: The workflow MUST report a pass or fail status on the pull request, and a failure MUST name the check or test that failed.
- **FR-013**: The workflow MUST wait until the database is ready before using it, so the result does not depend on startup timing.
- **FR-014**: The repository MUST offer three commands: one that runs every file check (lint, format, contract validation, path guard) over all tracked files, one that runs the secret and IP-address scan over a range of commits, and one that runs everything the workflow runs.
- **FR-015**: The workflow MUST call those two commands instead of repeating the list of checks, so there is one definition of "the checks".
- **FR-016**: The repository guide MUST document how to install the commit-stage checks, how to run the two commands, how to allow a reviewed false positive, and that bypassing the local stage is caught by the workflow.
- **FR-017**: All existing files MUST pass the checks when this phase ends, or be listed in a narrow, reviewed allowance with a reason, so the gates start green.
- **FR-018**: The checks MUST NOT print, log or commit any real field value from the raw export. Check output uses file names, line numbers, counts and reasons only.
- **FR-019**: The quality gates MUST NOT include the privacy test that fails when a restricted field appears in a curated layer (Phase 4) or the transformation-project build (Phase 3). Both MUST be addable later as one more step without redesigning the gates.
- **FR-020**: The tool for each check, the allowance format and the workflow platform details MUST be recorded in this phase's plan, not here, and any significant choice MUST be recorded as a decision record per the constitution.
- **FR-021**: During this phase, the whole commit history MUST be scanned once for secret-like values, for IPv4 addresses outside the reserved ranges and for files from the raw-data folder, and the result (clean, or each finding with its resolution) MUST be recorded in the phase's documents without printing any matched value. A real finding MUST be resolved (rotated or removed from history) before the phase ends.
- **FR-022**: After that audit, the workflow's secret scan MUST cover only the commits introduced by the pull request (or by the change reaching the main branch), not the whole history, so an old reviewed false positive cannot turn the status red permanently.
- **FR-023**: The commit stage MUST NOT run the full test suite and MUST NOT require the database to be running. The full test suite runs in the workflow and through the local pull-request command (FR-014).
- **FR-024**: The commit stage and the commit-range scan MUST refuse content that contains an IPv4 address outside the reserved ranges (documentation ranges 192.0.2.0/24, 198.51.100.0/24 and 203.0.113.0/24, loopback and the unspecified address). The message gives file and line and MUST NOT print the address. IPv6 stays covered by the existing repository hygiene test.

### Key Entities

- **Commit-stage check**: One automatic verification that runs on staged files before a commit. Attributes: what it verifies, the file types it applies to, whether it may fix files in place, what its failure message contains.
- **Workflow**: The automatic run triggered by a pull request or a change to the main branch. Attributes: trigger, ordered steps, environment (clean, no secrets), result status.
- **Check set**: The single definition of "all the checks" that both the commit stage and the workflow use. Attributes: member checks, the command that runs it locally.
- **Allowance**: A reviewed, narrow exception for a known false positive. Attributes: the file or pattern it covers, the check it applies to, the reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of attempts, a commit that stages a raw-data file, the local settings file or a secret-like value is refused, tested with all three forms plus a force-added raw-data file, and the refusal message never contains the matched value.
- **SC-002**: A commit of valid, documentation-only changes completes with the checks in under 5 seconds on the owner's machine, and a commit touching code and contracts in under 30 seconds.
- **SC-003**: An invalid data contract is refused at commit time in 100% of tested cases, and the message identifies what to fix.
- **SC-004**: A pull request with a failing test shows a failed status that names the failing test, and the same pull request after the fix shows a passed status, with no manual step between them.
- **SC-005**: The workflow finishes from trigger to result in under 10 minutes on a clean environment, with no real export and no real secret present.
- **SC-006**: A violation committed with the local stage bypassed is caught by the workflow in 100% of tested cases.
- **SC-007**: Every check the workflow runs is one of the checks of the three local commands (FR-014), and the workflow file lists no check itself: zero checks appear in one place and not the other.
- **SC-008**: On the day the phase ends, the all-checks command passes on the whole repository with zero unexplained allowances.
- **SC-009**: A new contributor can install the commit-stage checks and run both commands successfully by following only the repository guide, in under 10 minutes.
- **SC-010**: The one-time history audit finishes with zero unresolved real findings, and its record lists the number of commits scanned and the number of findings, with no matched value in it.

## Assumptions

- The repository is public and hosted on a platform that offers a workflow service for pull requests; the checks run there. The platform and tools are chosen in the plan step (the owner confirmed that tool choices belong in the plan).
- The workflow can start a database and the project's existing setup scripts in a clean environment, using the same container definition the owner uses locally.
- Throwaway credentials for the workflow are created inside the run and discarded with it. No repository secret is needed for this phase.
- Pull requests from forks get no secrets, which is acceptable because the workflow needs none.
- The existing repository hygiene test (no real IP addresses in tracked files) stays and runs as part of the test suite; the commit-stage scan now also refuses IPv4 addresses (FR-024), so the test remains as a second layer and as the only IPv6 check.
- The contract validation already exists as a project command from Phase 2; this phase calls it, it does not redefine it.
- Branch protection (making the status required to merge) is a repository setting, not a file. This phase documents the recommended setting and the owner decides whether to enable it.
- The checks work offline except for installing their tools the first time; the workflow downloads tools each run unless the plan adds caching.
- Out of scope: the privacy test over curated layers (Phase 4), the transformation project's own build and tests (Phase 3 adds them as one more workflow step), deployment or release automation, dependency update automation, code coverage thresholds and any notification outside the pull request status.
