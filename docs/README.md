# docs

Project documentation, grouped by kind.

## adr/ — Architecture Decision Records

Significant decisions are recorded here, as the project constitution requires.

| ADR | Decision |
| --- | --- |
| [0001](adr/0001-dbt-v2-experimental-postgres.md) | Use dbt v2 with the experimental Postgres adapter |
| [0002](adr/0002-quality-gates-tooling.md) | Quality gates with pre-commit, gitleaks, ruff, sqlfluff and GitHub Actions |

## guides/ — How to work with the project

| Document | Content |
| --- | --- |
| [quality-gates.md](guides/quality-gates.md) | Pre-commit checks, `make lint`, `make scan`, `make pr-check`, CI, allowing a false positive |

## reference/ — How it is built

| Document | Content |
| --- | --- |
| [architecture.md](reference/architecture.md) | Components, data flow, governance and eval design, with diagrams |
| [real-export-findings.md](reference/real-export-findings.md) | Structure and counts of the real Spotify export (no personal data) |
