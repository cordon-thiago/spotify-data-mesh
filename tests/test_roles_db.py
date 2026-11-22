"""Permission tests: connect as each real role and assert what the database allows.

The proof is the error the database returns (SQLSTATE 42501, insufficient privilege),
not a reading of the catalog. Error text is never printed or compared, because database
errors can echo values.

Every test works on throwaway objects with a unique prefix. The owner's real table
raw.spotify_streams is never dropped, truncated or altered here, and the table script
(make raw-table) is never run. Tests are skipped when the database or the roles are
missing (run make up and make roles).
"""

import os
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import errors

REPO_ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_PORT", "DBT_PASSWORD", "AGENT_PASSWORD"]
# Documentation-range addresses only (RFC 5737): never a real IP address.
DOC_ADDRESSES = ["203.0.113.1", "198.51.100.1", "192.0.2.1"]


def read_settings():
    """Settings from the environment, falling back to .env."""
    values = {}
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return {key: os.environ.get(key) or values.get(key) for key in SETTINGS if os.environ.get(key) or values.get(key)}


def connect(settings, user, password):
    return psycopg.connect(
        host="127.0.0.1",
        port=settings.get("POSTGRES_PORT", "5432"),
        user=user,
        password=password,
        dbname=settings.get("POSTGRES_DB", "spotify_mesh"),
        connect_timeout=3,
        autocommit=True,
    )


def refused(conn, sql):
    """True when the database refuses the statement for lack of privilege, False when it runs.

    Any other error propagates. Neither the statement result nor the error text is returned.
    """
    try:
        conn.execute(sql)
    except errors.InsufficientPrivilege:
        return True
    return False


@pytest.fixture(scope="module")
def settings():
    found = read_settings()
    for key in ("POSTGRES_PASSWORD", "DBT_PASSWORD", "AGENT_PASSWORD"):
        if key not in found:
            pytest.skip(f"{key} not set: see .env.example, then run make roles")
    return found


@pytest.fixture(scope="module")
def owner(settings):
    try:
        conn = connect(settings, settings.get("POSTGRES_USER", "owner"), settings["POSTGRES_PASSWORD"])
    except psycopg.OperationalError:
        pytest.skip("database not reachable: run make up")
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def dbt(settings, owner):
    try:
        conn = connect(settings, "dbt", settings["DBT_PASSWORD"])
    except psycopg.OperationalError:
        pytest.skip("role dbt cannot connect: run make roles")
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def agent(settings, owner):
    try:
        conn = connect(settings, "agent", settings["AGENT_PASSWORD"])
    except psycopg.OperationalError:
        pytest.skip("role agent cannot connect: run make roles")
    yield conn
    conn.close()


def make_raw_table(owner):
    name = f"raw.t_{uuid.uuid4().hex[:8]}"
    owner.execute(f"CREATE TABLE {name} (ts timestamptz, ip_addr inet, conn_country text)")
    for address in DOC_ADDRESSES:
        owner.execute(f"INSERT INTO {name} VALUES (now(), '{address}', 'PT')")
    return name


@pytest.fixture
def raw_table(owner):
    name = make_raw_table(owner)
    yield name
    owner.execute(f"DROP TABLE IF EXISTS {name}")


@pytest.fixture
def cleanup(owner):
    """Names of objects a test created; the owner drops them afterwards."""
    created = []
    yield created
    for kind, name in created:
        owner.execute(f"DROP {kind} IF EXISTS {name} CASCADE")


def unique(layer):
    return f"{layer}.t_{uuid.uuid4().hex[:8]}"


# --- smoke --------------------------------------------------------------------------------


def test_roles_can_connect(dbt, agent):
    assert dbt.execute("select 1").fetchone() == (1,)
    assert agent.execute("select 1").fetchone() == (1,)


# --- User Story 1: the agent cannot read restricted data -------------------------------------


def test_owner_reads_ip_addr(owner, raw_table):
    assert not refused(owner, f"select ip_addr from {raw_table}")


@pytest.mark.parametrize("query", ["select ip_addr from {t}", "select * from {t}", "select count(*) from {t}"])
def test_agent_cannot_read_raw(agent, raw_table, query):
    assert refused(agent, query.format(t=raw_table))


def test_agent_cannot_read_staging(agent, owner, cleanup):
    name = unique("staging")
    cleanup.append(("TABLE", name))
    owner.execute(f"CREATE TABLE {name} (x int)")
    assert refused(agent, f"select * from {name}")


def test_agent_has_no_grant_on_raw_or_staging(owner, agent):
    """Covers every table that exists now, including the real raw.spotify_streams if loaded."""
    for layer in ("raw", "staging"):
        assert not owner.execute("select has_schema_privilege('agent', %s, 'USAGE')", (layer,)).fetchone()[0]
        tables = owner.execute(
            "select schemaname || '.' || tablename from pg_tables where schemaname = %s", (layer,)
        ).fetchall()
        for (name,) in tables:
            assert refused(agent, f"select * from {name} limit 0")


@pytest.mark.parametrize("layer", ["raw", "staging", "marts", "semantic"])
def test_agent_cannot_create(agent, layer):
    assert refused(agent, f"create table {unique(layer)} (x int)")
    assert refused(agent, f"create view {unique(layer)} as select 1 as x")


@pytest.mark.parametrize(
    "statement",
    [
        "insert into {t} (conn_country) values ('PT')",
        "update {t} set conn_country = 'ES'",
        "delete from {t}",
        "truncate {t}",
        "drop table {t}",
    ],
)
def test_agent_cannot_write_raw(agent, raw_table, statement):
    assert refused(agent, statement.format(t=raw_table))


def test_agent_cannot_use_temp_tables_or_create_roles(agent):
    assert refused(agent, "create temporary table t_agent_tmp (x int)")
    assert refused(agent, f"create role r_{uuid.uuid4().hex[:8]}")


def test_nothing_is_open_to_public(agent, owner, cleanup):
    """Objects the owner creates in the curated layers grant nothing to anyone else."""
    for layer in ("marts", "semantic"):
        name = unique(layer)
        cleanup.append(("TABLE", name))
        owner.execute(f"CREATE TABLE {name} (x int)")
        assert refused(agent, f"select * from {name}")


# --- User Story 2: the pipeline role builds and nothing more -----------------------------------


def test_dbt_reads_raw(dbt, raw_table):
    assert not refused(dbt, f"select ip_addr from {raw_table}")


def test_dbt_builds_in_all_curated_layers(dbt, raw_table, cleanup):
    view = unique("staging")
    mart = unique("marts")
    sem = unique("semantic")
    cleanup += [("VIEW", view), ("TABLE", mart), ("VIEW", sem)]
    assert not refused(dbt, f"create view {view} as select ts, conn_country from {raw_table}")
    assert not refused(dbt, f"create table {mart} as select conn_country from {view}")
    assert not refused(dbt, f"create view {sem} as select conn_country from {mart}")
    for name in (view, mart, sem):
        assert not refused(dbt, f"select * from {name}")


def test_dbt_can_rebuild_a_table(dbt, cleanup):
    name = unique("marts")
    cleanup += [("TABLE", name), ("TABLE", name + "_new")]
    assert not refused(dbt, f"create table {name} as select 1 as x")
    assert not refused(dbt, f"create table {name}_new as select 2 as x")
    assert not refused(dbt, f"drop table {name}")
    assert not refused(dbt, f"alter table {name}_new rename to {name.split('.')[1]}")
    assert not refused(dbt, f"select * from {name}")


@pytest.mark.parametrize(
    "statement",
    [
        "insert into {t} (conn_country) values ('PT')",
        "update {t} set conn_country = 'ES'",
        "delete from {t}",
        "truncate {t}",
        "drop table {t}",
    ],
)
def test_dbt_cannot_change_raw(dbt, raw_table, statement):
    assert refused(dbt, statement.format(t=raw_table))


def test_dbt_cannot_create_in_raw_or_create_roles(dbt):
    assert refused(dbt, f"create table {unique('raw')} (x int)")
    assert refused(dbt, f"create role r_{uuid.uuid4().hex[:8]}")


def test_dbt_cannot_open_raw_to_the_agent(dbt, agent, raw_table):
    """PostgreSQL may answer a grant without grant option with a warning, not an error.

    Either way the grant must have no effect, which is what matters.
    """
    refused(dbt, f"grant select on {raw_table} to agent")
    refused(dbt, "grant usage on schema raw to agent")
    assert refused(agent, f"select * from {raw_table}")


def test_agent_reads_dbt_objects_in_curated_layers_without_a_grant(dbt, agent, raw_table, cleanup):
    mart = unique("marts")
    sem = unique("semantic")
    cleanup += [("TABLE", mart), ("VIEW", sem)]
    dbt.execute(f"create table {mart} as select conn_country from {raw_table}")
    dbt.execute(f"create view {sem} as select conn_country from {mart}")
    assert not refused(agent, f"select * from {mart}")
    assert not refused(agent, f"select * from {sem}")


def test_agent_reads_a_rebuilt_table_without_a_grant(dbt, agent, cleanup):
    name = unique("marts")
    cleanup += [("TABLE", name), ("TABLE", name + "_new")]
    dbt.execute(f"create table {name} as select 1 as x")
    dbt.execute(f"create table {name}_new as select 2 as x")
    dbt.execute(f"drop table {name}")
    dbt.execute(f"alter table {name}_new rename to {name.split('.')[1]}")
    assert not refused(agent, f"select * from {name}")


def test_agent_cannot_read_dbt_staging_objects(dbt, agent, raw_table, cleanup):
    view = unique("staging")
    cleanup.append(("VIEW", view))
    dbt.execute(f"create view {view} as select ts, conn_country from {raw_table}")
    assert refused(agent, f"select * from {view}")


# --- User Story 4: repeatable setup --------------------------------------------------------------


def test_raw_table_recreated_keeps_permissions(owner, dbt, agent):
    """The raw table script drops and recreates the table; no extra step may be needed."""
    name = make_raw_table(owner)
    try:
        owner.execute(f"DROP TABLE {name}")
        owner.execute(f"CREATE TABLE {name} (ts timestamptz, ip_addr inet, conn_country text)")
        assert not refused(dbt, f"select * from {name}")
        assert refused(agent, f"select ip_addr from {name}")
    finally:
        owner.execute(f"DROP TABLE IF EXISTS {name}")


def make_env(settings):
    env = dict(os.environ)
    env.update({key: value for key, value in settings.items()})
    return env


def test_setup_is_idempotent(settings, agent, raw_table):
    result = subprocess.run(["make", "roles"], cwd=REPO_ROOT, env=make_env(settings), capture_output=True, text=True)
    assert result.returncode == 0
    for password in (settings["DBT_PASSWORD"], settings["AGENT_PASSWORD"], settings["POSTGRES_PASSWORD"]):
        assert password not in result.stdout + result.stderr
    assert refused(agent, f"select ip_addr from {raw_table}")


def test_setup_without_a_password_changes_nothing(settings):
    env = make_env(settings)
    env["DBT_PASSWORD"] = ""
    result = subprocess.run(["make", "roles", "DBT_PASSWORD="], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "DBT_PASSWORD" in result.stdout + result.stderr
    for password in (settings["AGENT_PASSWORD"], settings["POSTGRES_PASSWORD"]):
        assert password not in result.stdout + result.stderr
