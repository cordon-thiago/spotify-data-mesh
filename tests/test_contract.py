"""The spotify_streams data contract: lint, classification rules and drift against the table.

Rules are listed in specs/003-roles-and-grants/contracts/spotify-streams-contract.md.
Rules 1 and 4 to 9 need no database; the drift rules (2 and 3) are skipped when the
database or the raw table is missing. Only names and type strings are ever printed.
"""

import subprocess
from pathlib import Path

import psycopg
import pytest
import yaml

from test_roles_db import connect, read_settings

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT = REPO_ROOT / "contracts" / "spotify_streams.odcs.yaml"
CLASSIFICATIONS = {"restricted", "confidential", "internal"}
BOOLEANS = ["shuffle", "skipped", "offline", "incognito_mode"]


@pytest.fixture(scope="module")
def contract():
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def properties(contract):
    schema = contract["schema"]
    assert len(schema) == 1, "the contract describes one table"
    return {prop["name"]: prop for prop in schema[0]["properties"]}


def description_text(contract):
    """The contract description is an object (purpose, limitations, usage); join its parts."""
    description = contract["description"]
    parts = description.values() if isinstance(description, dict) else [description]
    return " ".join(str(part) for part in parts).lower()


def test_lint_passes():  # rule 1
    result = subprocess.run(
        ["uv", "run", "datacontract", "lint", str(CONTRACT)], cwd=REPO_ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, "datacontract lint failed: run make lint-contract"


def test_every_property_is_described(properties):  # rule 4
    missing = [name for name, prop in properties.items() if not str(prop.get("description", "")).strip()]
    assert not missing, f"properties without a description: {missing}"


def test_every_property_has_one_valid_classification(properties):  # rule 5
    bad = [name for name, prop in properties.items() if prop.get("classification") not in CLASSIFICATIONS]
    assert not bad, f"properties without a valid classification: {bad}"


def test_classification_of_the_sensitive_fields(properties):  # rule 6
    restricted = sorted(name for name, prop in properties.items() if prop["classification"] == "restricted")
    assert restricted == ["ip_addr"]
    assert properties["conn_country"]["classification"] == "confidential"
    others = {name for name in properties if name not in ("ip_addr", "conn_country")}
    assert all(properties[name]["classification"] == "internal" for name in others)


def test_access_roles(contract):  # rule 7
    roles = {role["role"]: role.get("access") for role in contract["roles"]}
    assert set(roles) == {"owner", "dbt"}
    assert roles["dbt"] == "read"
    text = description_text(contract)
    assert "agent" in text and "no access" in text


def test_future_identifying_fields_are_restricted_by_default(contract):  # rule 8
    description = description_text(contract)
    assert "user agent" in description and "username" in description and "restricted by default" in description


@pytest.mark.parametrize("name", BOOLEANS)
def test_null_boolean_means_unknown(properties, name):  # rule 9
    description = properties[name]["description"].lower()
    assert "null" in description and "unknown" in description


def test_contract_matches_the_table(contract, properties):  # rules 2 and 3
    settings = read_settings()
    if "POSTGRES_PASSWORD" not in settings:
        pytest.skip("database settings not found: see .env.example")
    try:
        conn = connect(settings, settings.get("POSTGRES_USER", "owner"), settings["POSTGRES_PASSWORD"])
    except psycopg.OperationalError:
        pytest.skip("database not reachable: run make up")
    with conn:
        rows = conn.execute(
            "select column_name, data_type from information_schema.columns "
            "where table_schema = 'raw' and table_name = 'spotify_streams'"
        ).fetchall()
    if not rows:
        pytest.skip("raw.spotify_streams does not exist: run make raw-table")
    table = dict(rows)
    only_in_table = sorted(set(table) - set(properties))
    only_in_contract = sorted(set(properties) - set(table))
    assert not only_in_table, f"fields in the table but not in the contract: {only_in_table}"
    assert not only_in_contract, f"fields in the contract but not in the table: {only_in_contract}"
    different = sorted(name for name, prop in properties.items() if prop["physicalType"] != table[name])
    assert not different, f"fields whose type differs from the table: {different}"
