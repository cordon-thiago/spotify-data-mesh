#!/usr/bin/env python3
"""Load Spotify streaming-history JSON files into the raw table, unchanged.

The loader reads one file at a time and streams the rows into Postgres with
COPY. It never creates or alters the table (the column list and types are the
owner's, see sql/raw_spotify_streams.sql) and it never prints field values:
output and errors contain file names, counts and error categories only.
See specs/002-raw-ingestion/contracts/ingest-cli.md.
"""

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

import psycopg
from psycopg import sql

SOURCE_FILE_COLUMN = "source_file"
BOOLEAN_FIELDS = ["shuffle", "skipped", "offline", "incognito_mode"]
DEFAULT_PATTERN = "streaming_history_*.json"
DEFAULT_TABLE = "raw.spotify_streams"


class IngestError(Exception):
    """A failure with a one-line message and the process exit code that goes with it.

    Exit codes: 1 counts differ, 2 bad input or configuration, 3 database error.
    """

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def find_files(source, pattern):
    """Return (matched, ignored) file paths under source, relative and sorted.

    The search is recursive and the file-name match is case-insensitive, because
    the export unpacks into a subfolder and its file names are capitalised.
    """
    source = Path(source)
    matched, ignored = [], []
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        relative = path.relative_to(source).as_posix()
        if fnmatch.fnmatchcase(path.name.lower(), pattern.lower()):
            matched.append(relative)
        else:
            ignored.append(relative)
    return matched, ignored


def read_records(path, name=None):
    """Read one export file: a JSON array of objects. Errors never quote file content."""
    name = name or Path(path).name
    try:
        # utf-8-sig tolerates a byte-order mark and changes nothing else.
        with open(path, encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as error:
        raise IngestError(2, f"error: invalid JSON in {name} at line {error.lineno}, column {error.colno}")
    except UnicodeDecodeError:
        raise IngestError(2, f"error: {name} is not valid UTF-8")
    if not isinstance(data, list) or not all(isinstance(record, dict) for record in data):
        raise IngestError(2, f"error: {name} is not an array of records")
    return data


def render(value):
    """Render a JSON value as the text Postgres converts by column type.

    null stays None (SQL NULL) and an empty string stays empty, so the two stay
    distinguishable. Booleans are sent as true/false, which boolean columns parse
    and text columns store exactly as the source said.
    """
    if value is None:
        return None
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def check_keys(record, data_columns, name):
    """The record's keys must equal the table's data columns exactly."""
    unknown = sorted(set(record) - set(data_columns))
    if unknown:
        raise IngestError(2, f"error: unknown key {unknown[0]} in {name}")
    missing = [column for column in data_columns if column not in record]
    if missing:
        raise IngestError(2, f"error: missing key {missing[0]} in {name}")


def filter_db_error(error, name):
    """Describe a database error without its text: Postgres quotes the offending value.

    Only the file, the exception class, the SQLSTATE and, when the diagnostic
    context has them, the COPY line and column name are kept.
    """
    state = getattr(error, "sqlstate", None) or "unknown"
    text = f"error: database error in {name}: {type(error).__name__} (SQLSTATE {state})"
    context = getattr(getattr(error, "diag", None), "context", None) or ""
    # Look only before the first colon: after it comes the quoted offending value.
    location = context.split(":", 1)[0]
    line = re.search(r"line (\d+)", location)
    column = re.search(r"column (\w+)", location)
    if line:
        text += f", line {line.group(1)}"
    if column:
        text += f", column {column.group(1)}"
    return text


def compare_counts(read, table):
    """Raise (exit code 1) unless source and table agree on every figure.

    Both arguments map a file name to {"rows": n, "nulls": {field: n}}.
    """
    if read != table:
        raise IngestError(1, "error: counts differ, load rolled back")


def split_table(table):
    schema, _, name = table.partition(".")
    if not schema or not name or "." in name:
        raise IngestError(2, f"error: --table must be schema.table, got {table}")
    return schema, name


def connect():
    """Connect with the POSTGRES_* settings that the Makefile takes from .env."""
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise IngestError(2, "error: POSTGRES_PASSWORD is not set - run cp .env.example .env")
    try:
        return psycopg.connect(
            host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            user=os.environ.get("POSTGRES_USER", "owner"),
            password=password,
            dbname=os.environ.get("POSTGRES_DB", "spotify_mesh"),
            connect_timeout=5,
        )
    except psycopg.OperationalError as error:
        raise IngestError(3, f"error: cannot connect to the database ({type(error).__name__}) - is it running? try make up")


def inspect_table(conn, table):
    """Return the table's data columns, in table order.

    Data columns are the ones the loader fills from the JSON: no default, not
    identity, not generated, and not source_file. Columns that fill themselves
    (a row id, a load timestamp) are left to the database.
    """
    schema, name = split_table(table)
    rows = conn.execute(
        """
        SELECT column_name, column_default IS NULL, is_identity, is_generated
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, name),
    ).fetchall()
    if not rows:
        raise IngestError(
            2, f"error: table {table} not found - write sql/raw_spotify_streams.sql and run make raw-table"
        )
    if SOURCE_FILE_COLUMN not in [row[0] for row in rows]:
        raise IngestError(2, f"error: column {SOURCE_FILE_COLUMN} missing in {table}")
    return [
        column
        for column, no_default, identity, generated in rows
        if column != SOURCE_FILE_COLUMN and no_default and identity == "NO" and generated == "NEVER"
    ]


def load_files(conn, table, source, files, data_columns):
    """Empty the table and stream every file into it, inside the caller's transaction.

    Returns {file: {"rows": n, "nulls": {boolean field: n}}} counted while reading.
    Each file is checked in full before its COPY starts, so a bad record is
    reported by us and never reaches the database.
    """
    boolean_fields = [field for field in BOOLEAN_FIELDS if field in data_columns]
    identifier = sql.Identifier(*split_table(table))
    copy_statement = sql.SQL("COPY {} ({}) FROM STDIN").format(
        identifier, sql.SQL(", ").join(sql.Identifier(c) for c in [*data_columns, SOURCE_FILE_COLUMN])
    )
    counts = {}
    with conn.cursor() as cursor:
        try:
            cursor.execute(sql.SQL("TRUNCATE {}").format(identifier))
        except psycopg.Error as error:
            raise IngestError(3, filter_db_error(error, table))
        for name in files:
            records = read_records(Path(source) / name, name)
            nulls = dict.fromkeys(boolean_fields, 0)
            for record in records:
                check_keys(record, data_columns, name)
                for field in boolean_fields:
                    if record[field] is None:
                        nulls[field] += 1
            try:
                with cursor.copy(copy_statement) as copy:
                    for record in records:
                        copy.write_row([render(record[c]) for c in data_columns] + [name])
            except psycopg.Error as error:
                raise IngestError(3, filter_db_error(error, name))
            counts[name] = {"rows": len(records), "nulls": nulls}
    return counts


def table_counts(conn, table, boolean_fields):
    """Rows and NULL counts per source_file, as the table now holds them."""
    nulls = [
        sql.SQL("count(*) FILTER (WHERE {} IS NULL)").format(sql.Identifier(field)) for field in boolean_fields
    ]
    query = sql.SQL("SELECT {source}, count(*){nulls} FROM {table} GROUP BY 1").format(
        source=sql.Identifier(SOURCE_FILE_COLUMN),
        nulls=sql.SQL("").join(sql.SQL(", ") + n for n in nulls),
        table=sql.Identifier(*split_table(table)),
    )
    try:
        rows = conn.execute(query).fetchall()
    except psycopg.Error as error:
        raise IngestError(3, filter_db_error(error, table))
    return {row[0]: {"rows": row[1], "nulls": dict(zip(boolean_fields, row[2:]))} for row in rows}


def format_report(source, table, files, ignored, read, loaded, result):
    """The report: file names and counts only. A null count shows file/table when they differ."""
    fields = list(next(iter(read.values()))["nulls"]) if read else []
    width = max([len(name) for name in files] + [len("TOTAL"), len("file")]) + 2
    header = ["file".ljust(width), "read".rjust(6), "loaded".rjust(7)] + [f"null {f}".rjust(len(f) + 6) for f in fields]
    lines = [f"source: {source}  table: {table}", "".join(header)]

    def cell(read_value, loaded_value, size):
        text = str(read_value) if read_value == loaded_value else f"{read_value}/{loaded_value}"
        return text.rjust(size)

    total_read = total_loaded = 0
    total_nulls = {f: [0, 0] for f in fields}
    for name in files:
        r = read.get(name, {"rows": 0, "nulls": dict.fromkeys(fields, 0)})
        t = loaded.get(name, {"rows": 0, "nulls": dict.fromkeys(fields, 0)})
        total_read += r["rows"]
        total_loaded += t["rows"]
        row = [name.ljust(width), str(r["rows"]).rjust(6), str(t["rows"]).rjust(7)]
        for f in fields:
            total_nulls[f][0] += r["nulls"][f]
            total_nulls[f][1] += t["nulls"][f]
            row.append(cell(r["nulls"][f], t["nulls"][f], len(f) + 6))
        lines.append("".join(row))
    total = ["TOTAL".ljust(width), str(total_read).rjust(6), str(total_loaded).rjust(7)]
    total += [cell(total_nulls[f][0], total_nulls[f][1], len(f) + 6) for f in fields]
    lines.append("".join(total))
    if ignored:
        lines.append("ignored: " + ", ".join(ignored))
    lines.append(f"result: {result}")
    return "\n".join(lines)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Load Spotify streaming history files into the raw table.")
    parser.add_argument("--source", default="sample_data", help="folder searched recursively for export files")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN, help="case-insensitive file-name glob")
    parser.add_argument("--table", default=DEFAULT_TABLE, help="target table, schema.table")
    return parser.parse_args(argv)


def run(args):
    """Load and verify. Commits only when every count matches; any failure leaves the table as it was."""
    source = Path(args.source)
    if not source.is_dir():
        raise IngestError(2, f"error: source folder {args.source} not found")
    conn = connect()
    try:
        data_columns = inspect_table(conn, args.table)
        files, ignored = find_files(source, args.pattern)
        if not files:
            raise IngestError(2, f"error: no files matching {args.pattern} found in {args.source}")
        read = load_files(conn, args.table, source, files, data_columns)
        boolean_fields = [field for field in BOOLEAN_FIELDS if field in data_columns]
        loaded = table_counts(conn, args.table, boolean_fields)
        try:
            compare_counts(read, loaded)
        except IngestError:
            print(format_report(args.source, args.table, files, ignored, read, loaded, "rolled back"))
            raise
        conn.commit()
        print(format_report(args.source, args.table, files, ignored, read, loaded, "committed"))
    finally:
        conn.close()  # closing without a commit rolls the transaction back


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        run(args)
    except IngestError as error:
        print(error.message, file=sys.stderr)
        return error.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
