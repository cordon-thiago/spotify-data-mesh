#!/usr/bin/env python3
"""Generate synthetic Spotify extended streaming history files.

The output has the same 23-field schema as the real export, but every value is
synthetic: names are made up, URIs are random, and IP addresses come only from
the RFC 5737 documentation ranges. The same --records and --seed always give
byte-identical files. See specs/001-local-dev-foundation/contracts/generator-cli.md.
"""

import argparse
import json
import random
import string
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

FIELDS = [
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
BOOLEANS = ["shuffle", "skipped", "offline", "incognito_mode"]

MIN_RECORDS = 100
MAX_RECORDS = 10_000_000
DEFAULT_RECORDS = 2000
DEFAULT_SEED = 42

AUDIO_FILE = "streaming_history_audio_sample.json"
VIDEO_FILE = "streaming_history_video_sample.json"

# Fixed window, so output never depends on the day the generator runs.
WINDOW_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
WINDOW_END = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
LISBON = ZoneInfo("Europe/Lisbon")

# RFC 5737 documentation ranges: cannot belong to a real device.
IP_PREFIXES = ["192.0.2", "198.51.100", "203.0.113"]
BASE62 = string.ascii_letters + string.digits

PLATFORMS = ["android", "ios", "windows", "OS X", "web_player"]
COUNTRIES = ["PT", "PT", "PT", "PT", "ES", "DE", "BR", "US"]
REASON_START = ["trackdone", "clickrow", "fwdbtn", "backbtn", "appload", "playbtn", "unknown"]
REASON_END = ["trackdone", "endplay", "fwdbtn", "backbtn", "logout", "unexpected-exit"]

# Share of music / podcast / audiobook streams in the random body.
MUSIC_SHARE = 0.80
PODCAST_SHARE = 0.15
NULL_SHARE = 0.05
INCOGNITO_SHARE = 0.03
OFFLINE_SHARE = 0.05
MISSING_OFFLINE_TIMESTAMP_SHARE = 0.10

CATALOG_TRACKS = 500
CATALOG_ARTISTS = 50
CATALOG_SHOWS = 20
EPISODES_PER_SHOW = 100
CATALOG_AUDIOBOOKS = 10
CHAPTERS_PER_AUDIOBOOK = 12

# Number of records in the fixed edge-case block (see edge_case_records).
EDGE_RECORDS = 23


def base62_id(rng):
    return "".join(rng.choices(BASE62, k=22))


def build_catalog(rng):
    """Fixed pools of tracks, episodes and audiobook chapters, so URIs repeat across streams."""
    tracks = [
        {
            "master_metadata_track_name": f"Synthetic Track {i:04d}",
            "master_metadata_album_artist_name": f"Synthetic Artist {i % CATALOG_ARTISTS + 1:02d}",
            "master_metadata_album_album_name": f"Synthetic Album {i // 5:03d}",
            "spotify_track_uri": f"spotify:track:{base62_id(rng)}",
        }
        for i in range(CATALOG_TRACKS)
    ]
    episodes = [
        {
            "episode_name": f"Synthetic Episode {s:02d}-{e:03d}",
            "episode_show_name": f"Synthetic Show {s:02d}",
            "spotify_episode_uri": f"spotify:episode:{base62_id(rng)}",
        }
        for s in range(CATALOG_SHOWS)
        for e in range(EPISODES_PER_SHOW)
    ]
    chapters = []
    for b in range(CATALOG_AUDIOBOOKS):
        book_uri = f"spotify:show:{base62_id(rng)}"
        for c in range(CHAPTERS_PER_AUDIOBOOK):
            chapters.append(
                {
                    "audiobook_title": f"Synthetic Audiobook {b:02d}",
                    "audiobook_uri": book_uri,
                    "audiobook_chapter_uri": f"spotify:episode:{base62_id(rng)}",
                    "audiobook_chapter_title": f"Chapter {c + 1}",
                }
            )
    return {"music": tracks, "podcast": episodes, "audiobook": chapters}


def format_ts(moment):
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def maybe_null(rng, value):
    return None if rng.random() < NULL_SHARE else value


def build_record(rng, catalog, kind, ts=None, ms_played=None):
    """One stream record of the given kind: music, podcast or audiobook."""
    if ts is None:
        span = int((WINDOW_END - WINDOW_START).total_seconds())
        ts = WINDOW_START + timedelta(seconds=rng.randrange(span))
    reason_end = rng.choice(REASON_END)
    skipped = reason_end == "fwdbtn"
    if ms_played is None:
        ms_played = rng.randint(1_000, 60_000) if skipped else rng.randint(30_000, 400_000)
    offline_timestamp = rng.randint(int(WINDOW_START.timestamp()), int(WINDOW_END.timestamp()))

    record = dict.fromkeys(FIELDS)
    record.update(
        ts=format_ts(ts),
        platform=rng.choice(PLATFORMS),
        ms_played=ms_played,
        conn_country=rng.choice(COUNTRIES),
        ip_addr=f"{rng.choice(IP_PREFIXES)}.{rng.randint(1, 254)}",
        reason_start=rng.choice(REASON_START),
        reason_end=reason_end,
        shuffle=maybe_null(rng, rng.random() < 0.5),
        skipped=maybe_null(rng, skipped),
        offline=maybe_null(rng, rng.random() < OFFLINE_SHARE),
        offline_timestamp=(
            None if rng.random() < MISSING_OFFLINE_TIMESTAMP_SHARE else offline_timestamp
        ),
        incognito_mode=maybe_null(rng, rng.random() < INCOGNITO_SHARE),
    )
    record.update(rng.choice(catalog[kind]))
    return record


def pick_kind(rng):
    draw = rng.random()
    if draw < MUSIC_SHARE:
        return "music"
    if draw < MUSIC_SHARE + PODCAST_SHARE:
        return "podcast"
    return "audiobook"


def local_to_utc(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=LISBON).astimezone(timezone.utc)


def edge_case_records(rng, catalog):
    """Fixed block of records that every dataset contains, whatever its size.

    Later phases rely on these to test null handling, the private-session
    policy, local-time conversion, deduplication and content-type filters.
    Yields (kind, record) pairs; exactly EDGE_RECORDS of them.
    """
    # A boolean that is null: 2 records for each of the 4 optional booleans (8).
    for name in BOOLEANS:
        for _ in range(2):
            record = build_record(rng, catalog, "music")
            record[name] = None
            yield "music", record

    # Private sessions (3).
    for _ in range(3):
        record = build_record(rng, catalog, "music")
        record["incognito_mode"] = True
        yield "music", record

    twenty_minutes = 20 * 60 * 1000
    # Streams that cross midnight in Lisbon local time (4). In winter Lisbon is UTC+0, so
    # local and UTC time agree. In summer (UTC+1) the stream ends at 23:xx UTC, so
    # converting with a fixed UTC offset would put it on the wrong day.
    crossings = [
        local_to_utc(2024, 12, 10, 0, 5),
        local_to_utc(2025, 1, 21, 0, 10),
        local_to_utc(2024, 7, 15, 0, 5),
        local_to_utc(2025, 8, 2, 0, 12),
    ]
    for end in crossings:
        yield "music", build_record(rng, catalog, "music", ts=end, ms_played=twenty_minutes)

    # Audiobook streams (3).
    for _ in range(3):
        yield "audiobook", build_record(rng, catalog, "audiobook")

    # A podcast show and a music artist with the same name (2).
    lookalike = "Synthetic Artist 07"
    music = build_record(rng, catalog, "music")
    music["master_metadata_album_artist_name"] = lookalike
    yield "music", music
    podcast = build_record(rng, catalog, "podcast")
    podcast["episode_show_name"] = lookalike
    yield "podcast", podcast

    # The 3 exact duplicates are added by generate_records, which owns the first records.


class JsonArrayWriter:
    """Write records one at a time as a JSON array with Spotify's `"key" : value` spacing."""

    def __init__(self, path):
        self.file = path.open("w", encoding="utf-8", newline="\n")
        self.count = 0

    def write(self, record):
        self.file.write("[\n" if self.count == 0 else ",\n")
        self.file.write(json.dumps(record, indent=2, ensure_ascii=False, separators=(",", " : ")))
        self.count += 1

    def close(self):
        self.file.write("[]\n" if self.count == 0 else "\n]\n")
        self.file.close()


def target_file(kind):
    return VIDEO_FILE if kind == "podcast" else AUDIO_FILE


def generate_records(records, seed):
    """Yield (kind, record) pairs: random body, edge-case block, then 3 duplicates."""
    rng = random.Random(seed)
    catalog = build_catalog(rng)
    first = []
    for _ in range(records - EDGE_RECORDS):
        kind = pick_kind(rng)
        record = build_record(rng, catalog, kind)
        if len(first) < 3:
            first.append((kind, record))
        yield kind, record
    yield from edge_case_records(rng, catalog)
    yield from first


def write_dataset(out_dir, records, seed):
    out_dir.mkdir(parents=True, exist_ok=True)
    writers = {name: JsonArrayWriter(out_dir / name) for name in (AUDIO_FILE, VIDEO_FILE)}
    try:
        for kind, record in generate_records(records, seed):
            writers[target_file(kind)].write(record)
    finally:
        for writer in writers.values():
            writer.close()
    return {name: writer.count for name, writer in writers.items()}


def is_inside_data_folder(out):
    """True when --out is the repository's data/ folder or inside it (where the real export lives)."""
    data_dir = (Path(__file__).resolve().parent.parent / "data").resolve()
    resolved = (Path.cwd() / out).resolve()
    return resolved == data_dir or data_dir in resolved.parents or Path(out).parts[:1] == ("data",)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Generate synthetic Spotify streaming history files.")
    parser.add_argument("--records", default=str(DEFAULT_RECORDS), help="records to generate, 100 to 10000000")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed")
    parser.add_argument("--out", default="sample_data", help="output directory")
    args = parser.parse_args(argv)
    try:
        records = int(args.records)
    except ValueError:
        records = None
    if records is None or not MIN_RECORDS <= records <= MAX_RECORDS:
        parser.error(f"--records must be between {MIN_RECORDS} and {MAX_RECORDS}")
    if is_inside_data_folder(args.out):
        parser.error("refusing to write sample data into data/")
    args.records = records
    return args


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    counts = write_dataset(Path(args.out), args.records, args.seed)
    for name, count in counts.items():
        print(f"{Path(args.out) / name}: {count} records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
