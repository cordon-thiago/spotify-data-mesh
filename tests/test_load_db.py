"""Integration tests for ingest/load.py against the Phase 0 database.

Every test works in a throwaway schema. The tables created here are test
fixtures with all-text columns; they are NOT a design for raw.spotify_streams,
whose definition is the owner's (sql/raw_spotify_streams.sql). The tests are
skipped when the database is not reachable (run `make up`).
"""

import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest

from generate import FIELDS

REPO_ROOT = Path(__file__).resolve().parents[1]
LOADER = REPO_ROOT / "ingest" / "load.py"
GENERATOR = REPO_ROOT / "sample_data" / "generate.py"
BOOLEANS = ["shuffle", "skipped", "offline", "incognito_mode"]
SETTINGS = ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_PORT"]


def connection_settings():
    """Connection settings from the environment, falling back to .env."""
    values = {}
    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return {key: os.environ.get(key, values.get(key)) for key in SETTINGS if os.environ.get(key, values.get(key))}


@pytest.fixture(scope="module")
def settings():
    found = connection_settings()
    if "POSTGRES_PASSWORD" not in found:
        pytest.skip("database settings not found: run cp .env.example .env")
    return found


@pytest.fixture(scope="module")
def db(settings):
    try:
        conn = psycopg.connect(
            host="127.0.0.1",
            port=settings.get("POSTGRES_PORT", "5432"),
            user=settings.get("POSTGRES_USER", "owner"),
            password=settings["POSTGRES_PASSWORD"],
            dbname=settings.get("POSTGRES_DB", "spotify_mesh"),
            connect_timeout=3,
            autocommit=True,
        )
    except psycopg.OperationalError:
        pytest.skip("database not reachable: run make up")
    yield conn
    conn.close()


@pytest.fixture
def schema(db):
    name = f"test_raw_{uuid.uuid4().hex[:8]}"
    db.execute(f'CREATE SCHEMA "{name}"')
    yield name
    db.execute(f'DROP SCHEMA "{name}" CASCADE')


@pytest.fixture
def make_table(db, schema):
    """Create a fixture table: the sample fields plus source_file, all text unless told otherwise."""

    def factory(name="spotify_streams", with_source_file=True, types=None):
        types = types or {}
        columns = [f'"{field}" {types.get(field, "text")}' for field in FIELDS]
        if with_source_file:
            columns.append("source_file text")
        db.execute(f'CREATE TABLE "{schema}"."{name}" ({", ".join(columns)})')
        return f"{schema}.{name}"

    return factory


@pytest.fixture
def sample_dir(tmp_path):
    out = tmp_path / "sample"
    subprocess.run(
        [sys.executable, str(GENERATOR), "--records", "100", "--out", str(out)],
        check=True,
        capture_output=True,
    )
    return out


def run_load(settings, table, source, *extra, drop=()):
    env = {**os.environ, **{key: value for key, value in settings.items() if key not in drop}}
    for key in drop:
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, str(LOADER), "--source", str(source), "--table", table, *extra],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )
    return result


def everything(result):
    return result.stdout + result.stderr


def json_counts(source):
    """Records and boolean None counts per relative file name, read straight from the JSON."""
    counts = {}
    for path in sorted(Path(source).rglob("*.json")):
        records = json.loads(path.read_text(encoding="utf-8"))
        counts[path.relative_to(source).as_posix()] = {
            "rows": len(records),
            "nulls": {f: sum(1 for r in records if r[f] is None) for f in BOOLEANS},
        }
    return counts


def table_counts(db, table):
    schema, name = table.split(".")
    nulls = ", ".join(f'count(*) FILTER (WHERE "{f}" IS NULL)' for f in BOOLEANS)
    rows = db.execute(
        f'SELECT source_file, count(*), {nulls} FROM "{schema}"."{name}" GROUP BY 1 ORDER BY 1'
    ).fetchall()
    return {r[0]: {"rows": r[1], "nulls": dict(zip(BOOLEANS, r[2:]))} for r in rows}


def total_rows(db, table):
    schema, name = table.split(".")
    return db.execute(f'SELECT count(*) FROM "{schema}"."{name}"').fetchone()[0]


def test_rows_loaded_equal_records_read_per_file_and_in_total(db, settings, make_table, sample_dir):
    table = make_table()
    result = run_load(settings, table, sample_dir)
    assert result.returncode == 0, everything(result)
    expected = json_counts(sample_dir)
    assert table_counts(db, table) == expected
    assert total_rows(db, table) == sum(c["rows"] for c in expected.values()) == 100
    assert "result: committed" in result.stdout
    total_line = next(line for line in result.stdout.splitlines() if line.startswith("TOTAL"))
    assert total_line.split()[1:3] == ["100", "100"]
    for name in expected:
        assert name in result.stdout


def test_null_booleans_stay_null_and_are_counted(db, settings, make_table, sample_dir):
    table = make_table()
    assert run_load(settings, table, sample_dir).returncode == 0
    schema, name = table.split(".")
    expected = json_counts(sample_dir)
    for field in BOOLEANS:
        assert sum(c["nulls"][field] for c in expected.values()) >= 2  # the generator guarantees it
        in_table = db.execute(f'SELECT count(*) FROM "{schema}"."{name}" WHERE "{field}" IS NULL').fetchone()[0]
        assert in_table == sum(c["nulls"][field] for c in expected.values())
        # A null must not have turned into false or an empty string.
        falses = db.execute(f"SELECT count(*) FROM \"{schema}\".\"{name}\" WHERE \"{field}\" IN ('false', '')").fetchone()[0]
        source_falses = sum(
            1
            for path in Path(sample_dir).rglob("*.json")
            for r in json.loads(path.read_text(encoding="utf-8"))
            if r[field] is False
        )
        assert falses == source_falses


def test_duplicate_records_are_loaded_as_they_are(db, settings, make_table, sample_dir):
    table = make_table()
    assert run_load(settings, table, sample_dir).returncode == 0
    schema, name = table.split(".")
    columns = ", ".join(f'"{f}"' for f in FIELDS)
    distinct = db.execute(
        f'SELECT count(*) FROM (SELECT DISTINCT {columns} FROM "{schema}"."{name}") d'
    ).fetchone()[0]
    assert distinct <= total_rows(db, table) - 3


def test_running_the_load_twice_leaves_the_same_rows(db, settings, make_table, sample_dir):
    table = make_table()
    assert run_load(settings, table, sample_dir).returncode == 0
    first = table_counts(db, table)
    assert run_load(settings, table, sample_dir).returncode == 0
    assert table_counts(db, table) == first
    assert total_rows(db, table) == 100


def test_source_file_holds_the_relative_path(db, settings, make_table, sample_dir):
    nested = sample_dir.parent / "nested"
    (nested / "export").mkdir(parents=True)
    for path in sample_dir.glob("*.json"):
        (nested / "export" / path.name).write_bytes(path.read_bytes())
    table = make_table()
    assert run_load(settings, table, nested).returncode == 0
    assert all(name.startswith("export/") for name in table_counts(db, table))


def test_missing_table_stops_before_reading_data(db, settings, schema, sample_dir):
    result = run_load(settings, f"{schema}.does_not_exist", sample_dir)
    assert result.returncode == 2
    assert "sql/raw_spotify_streams.sql" in everything(result)
    assert "make raw-table" in everything(result)


def test_missing_source_file_column_is_reported(settings, make_table, sample_dir):
    table = make_table(with_source_file=False)
    result = run_load(settings, table, sample_dir)
    assert result.returncode == 2
    assert f"error: column source_file missing in {table}" in everything(result)


def test_no_matching_files_is_reported(settings, make_table, tmp_path):
    table = make_table()
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    result = run_load(settings, table, tmp_path)
    assert result.returncode == 2
    assert "error: no files matching streaming_history_*.json found in" in everything(result)


def test_missing_password_is_reported(settings, make_table, sample_dir):
    table = make_table()
    result = run_load(settings, table, sample_dir, drop=("POSTGRES_PASSWORD",))
    assert result.returncode == 2
    assert "error: POSTGRES_PASSWORD is not set" in everything(result)


def modify_first_record(source, edit):
    path = sorted(Path(source).glob("*audio*.json"))[0]
    records = json.loads(path.read_text(encoding="utf-8"))
    edit(records[0])
    path.write_text(json.dumps(records), encoding="utf-8")
    return path.name


def test_unknown_key_stops_the_load_and_keeps_previous_content(db, settings, make_table, sample_dir):
    table = make_table()
    assert run_load(settings, table, sample_dir).returncode == 0
    before = table_counts(db, table)
    name = modify_first_record(sample_dir, lambda record: record.update(extra_field="x"))
    result = run_load(settings, table, sample_dir)
    assert result.returncode == 2
    assert f"error: unknown key extra_field in {name}" in everything(result)
    assert table_counts(db, table) == before


def test_missing_key_stops_the_load(db, settings, make_table, sample_dir):
    table = make_table()
    name = modify_first_record(sample_dir, lambda record: record.pop("shuffle"))
    result = run_load(settings, table, sample_dir)
    assert result.returncode == 2
    assert f"error: missing key shuffle in {name}" in everything(result)
    assert total_rows(db, table) == 0


def test_malformed_file_rolls_back_to_the_previous_load(db, settings, make_table, sample_dir):
    table = make_table()
    assert run_load(settings, table, sample_dir).returncode == 0
    before = table_counts(db, table)
    (sample_dir / "streaming_history_zz_broken.json").write_text('[{"ts": "SECRETMARKER9"', encoding="utf-8")
    result = run_load(settings, table, sample_dir)
    assert result.returncode == 2
    assert "error: invalid JSON in streaming_history_zz_broken.json at line 1, column" in everything(result)
    assert "SECRETMARKER9" not in everything(result)
    assert table_counts(db, table) == before


def test_database_errors_never_print_the_offending_value(db, settings, make_table, sample_dir):
    table = make_table(types={"ms_played": "integer"})
    name = modify_first_record(sample_dir, lambda record: record.update(ms_played="SECRETMARKER9"))
    result = run_load(settings, table, sample_dir)
    assert result.returncode == 3
    output = everything(result)
    assert name in output
    assert "22P02" in output
    assert "column ms_played" in output
    assert "SECRETMARKER9" not in output
    assert total_rows(db, table) == 0


def test_successful_output_has_names_and_counts_only(settings, make_table, sample_dir):
    table = make_table()
    result = run_load(settings, table, sample_dir)
    assert result.returncode == 0
    output = everything(result)
    assert "Synthetic" not in output
    assert not re.search(r"(192\.0\.2|198\.51\.100|203\.0\.113)\.\d+", output)


def test_count_mismatch_rolls_back_and_exits_with_code_1(db, settings, schema, make_table, sample_dir):
    table = make_table()
    assert run_load(settings, table, sample_dir).returncode == 0
    before = table_counts(db, table)
    # A trigger that silently drops half the rows makes the table disagree with the files.
    db.execute(
        f'CREATE FUNCTION "{schema}".skip_rows() RETURNS trigger LANGUAGE plpgsql AS '
        "$$ BEGIN IF random() < 0.5 THEN RETURN NULL; END IF; RETURN NEW; END $$"
    )
    db.execute(
        f'CREATE TRIGGER skip BEFORE INSERT ON "{schema}".spotify_streams '
        f'FOR EACH ROW EXECUTE FUNCTION "{schema}".skip_rows()'
    )
    result = run_load(settings, table, sample_dir)
    assert result.returncode == 1
    assert "error: counts differ, load rolled back" in result.stderr
    assert "result: rolled back" in result.stdout
    assert re.search(r"\d+/\d+", result.stdout)  # a differing figure is shown as file/table
    assert table_counts(db, table) == before
