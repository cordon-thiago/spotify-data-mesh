"""Quality gates: the check set, the path guard and the single definition of "the checks".

These tests read the configuration files; they do not need the database. They make the table in
specs/004-quality-gates/contracts/check-set.md and the files in the repository agree.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"


def load_hooks():
    """Every hook of .pre-commit-config.yaml as a dict, keyed by hook id."""
    config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    return {hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]}


# Rows of the "Forbidden paths" table in contracts/check-set.md.
REFUSED_PATHS = [
    "data/streaming_history_0.json",
    ".env",
    ".env.ci",
    ".claude/settings.local.json",
    "server.key",
]
ACCEPTED_PATHS = [
    "data/README.md",
    ".env.example",
    "sample_data/streaming_history_audio_sample.json",
]


@pytest.fixture(scope="module")
def path_guard():
    return re.compile(load_hooks()["path-guard"]["files"])


@pytest.mark.parametrize("path", REFUSED_PATHS)
def test_path_guard_refuses_forbidden_path(path_guard, path):
    assert path_guard.search(path), f"{path} must be refused by the path guard"


@pytest.mark.parametrize("path", ACCEPTED_PATHS)
def test_path_guard_accepts_allowed_path(path_guard, path):
    assert not path_guard.search(path), f"{path} must be accepted by the path guard"


def test_path_guard_always_fails_on_a_match():
    """language: fail makes the hook fail for every matching file, whatever its content."""
    assert load_hooks()["path-guard"]["language"] == "fail"


# The nine checks of contracts/check-set.md.
EXPECTED_HOOK_IDS = {
    "path-guard",
    "gitleaks",
    "check-merge-conflict",
    "check-added-large-files",
    "ruff-check",
    "ruff-format",
    "sqlfluff-lint",
    "yamllint",
    "contract-lint",
}


def test_hook_ids_match_the_check_set():
    assert set(load_hooks()) == EXPECTED_HOOK_IDS


def test_contract_lint_only_matches_contracts():
    pattern = re.compile(load_hooks()["contract-lint"]["files"])
    assert pattern.search("contracts/spotify_streams.odcs.yaml")
    assert not pattern.search("docker-compose.yml")
    assert not pattern.search("contracts/README.md")


# The workflow is the same check set as the local commands: it names no check itself (SC-007).
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CHECK_NAMES = ["ruff", "sqlfluff", "yamllint", "pytest", "datacontract", "pre-commit run"]


@pytest.fixture(scope="module")
def workflow_text():
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_names_no_individual_check(workflow_text):
    present = [name for name in CHECK_NAMES if name in workflow_text]
    assert not present, f"the workflow must call make pr-check, not list checks: {present}"


def test_workflow_calls_only_make_pr_check(workflow_text):
    assert set(re.findall(r"\bmake\s+([\w-]+)", workflow_text)) == {"pr-check"}


def test_workflow_is_read_only_and_not_pull_request_target(workflow_text):
    workflow = yaml.safe_load(workflow_text)
    assert workflow["permissions"] == {"contents": "read"}
    assert "pull_request_target" not in workflow_text


def test_workflow_has_one_job_named_checks():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert list(workflow["jobs"]) == ["checks"]


def test_workflow_actions_are_pinned_to_a_commit(workflow_text):
    uses = re.findall(r"^\s*-?\s*uses:\s*(\S+)", workflow_text, flags=re.MULTILINE)
    assert uses, "expected at least one action"
    for action in uses:
        assert re.search(r"@[0-9a-f]{40}$", action), f"{action} must be pinned to a full commit SHA"
