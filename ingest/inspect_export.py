#!/usr/bin/env python3
"""Show the structure of a Spotify export folder, without showing any value.

For each streaming-history file it prints the record count, and for every JSON
key how many records have it, which JSON types it holds and how many nulls.
It also shows which content types the records fill and how the keys differ
from the 23 fields of the sample schema. Only names, counts and types are
printed, so it is safe to run on the real export.
See specs/002-raw-ingestion/contracts/ingest-cli.md.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from load import DEFAULT_PATTERN, IngestError, find_files, read_records

# The 23 fields of the sample schema (kept equal to sample_data/generate.py by a test).
EXPECTED_FIELDS = [
    "ts",
    "platform",
    "ms_played",
    "conn_country",
    "ip_addr",
    "master_metadata_track_name",
    "master_metadata_album_artist_name",
    "master_metadata_album_album_name",
    "spotify_track_uri",
    "episode_name",
    "episode_show_name",
    "spotify_episode_uri",
    "audiobook_title",
    "audiobook_uri",
    "audiobook_chapter_uri",
    "audiobook_chapter_title",
    "reason_start",
    "reason_end",
    "shuffle",
    "skipped",
    "offline",
    "offline_timestamp",
    "incognito_mode",
]
CONTENT_GROUPS = {
    "music": EXPECTED_FIELDS[5:9],
    "podcast": EXPECTED_FIELDS[9:12],
    "audiobook": EXPECTED_FIELDS[12:16],
}


def json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):  # before int: bool is a subclass of int
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    return "array"


def describe(records):
    """Per key: records having it, JSON types seen, nulls. Plus the content-group counts."""
    keys = {}
    content = Counter()
    for record in records:
        for key, value in record.items():
            stats = keys.setdefault(key, {"present": 0, "types": set(), "nulls": 0})
            stats["present"] += 1
            stats["types"].add(json_type(value))
            stats["nulls"] += value is None
        filled = [group for group, fields in CONTENT_GROUPS.items() if any(record.get(f) is not None for f in fields)]
        content["none" if not filled else "several" if len(filled) > 1 else filled[0]] += 1
    return keys, content


def format_file(name, size_mb, count, keys, content):
    width = max([len(key) for key in keys] + [len("key")]) + 2
    lines = [
        f"file: {name}  ({size_mb:.2f} MB, {count} records)",
        f"  {'key'.ljust(width)}{'records'.rjust(8)}  {'types'.ljust(24)}{'nulls'.rjust(6)}",
    ]
    for key, stats in keys.items():
        types = ",".join(sorted(stats["types"]))
        lines.append(f"  {key.ljust(width)}{str(stats['present']).rjust(8)}  {types.ljust(24)}{str(stats['nulls']).rjust(6)}")
    outside = [key for key in keys if key not in EXPECTED_FIELDS]
    absent = [field for field in EXPECTED_FIELDS if field not in keys]
    lines.append(f"  outside the 23 sample fields: {', '.join(outside) or '(none)'}")
    lines.append(f"  absent sample fields: {', '.join(absent) or '(none)'}")
    groups = ["music", "podcast", "audiobook", "none", "several"]
    lines.append("  content: " + ", ".join(f"{group} {content[group]}" for group in groups))
    return "\n".join(lines)


def inspect_folder(source, pattern):
    source = Path(source)
    if not source.is_dir():
        raise IngestError(2, f"error: source folder {source} not found")
    files, ignored = find_files(source, pattern)
    if not files:
        raise IngestError(2, f"error: no files matching {pattern} found in {source}")
    sections, total_records, total_mb, largest = [], 0, 0.0, 0.0
    all_outside, all_absent = set(), set(EXPECTED_FIELDS)
    for name in files:
        path = source / name
        records = read_records(path, name)
        keys, content = describe(records)
        size_mb = path.stat().st_size / (1024 * 1024)
        sections.append(format_file(name, size_mb, len(records), keys, content))
        total_records += len(records)
        total_mb += size_mb
        largest = max(largest, size_mb)
        all_outside |= {key for key in keys if key not in EXPECTED_FIELDS}
        all_absent &= {field for field in EXPECTED_FIELDS if field not in keys}
    summary = [
        f"TOTAL: {len(files)} files, {total_records} records, {total_mb:.2f} MB (largest file {largest:.2f} MB)",
        f"keys outside the 23 sample fields in any file: {', '.join(sorted(all_outside)) or '(none)'}",
        f"sample fields absent from every file: {', '.join(f for f in EXPECTED_FIELDS if f in all_absent) or '(none)'}",
    ]
    if ignored:
        summary.append("ignored: " + ", ".join(ignored))
    return "\n\n".join(sections) + "\n\n" + "\n".join(summary)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Show the structure of a Spotify export folder (no values).")
    parser.add_argument("source", help="folder with the export files")
    parser.add_argument("--pattern", default=DEFAULT_PATTERN, help="case-insensitive file-name glob")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        print(inspect_folder(args.source, args.pattern))
    except IngestError as error:
        print(error.message, file=sys.stderr)
        return error.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
