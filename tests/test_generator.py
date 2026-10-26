"""Tests for the synthetic sample data generator (sample_data/generate.py).

The generator is exercised through its command line, as documented in
specs/001-local-dev-foundation/contracts/generator-cli.md.
"""

import ipaddress
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "sample_data" / "generate.py"
AUDIO_FILE = "streaming_history_audio_sample.json"
VIDEO_FILE = "streaming_history_video_sample.json"

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
MUSIC = FIELDS[5:9]
PODCAST = FIELDS[9:12]
AUDIOBOOK = FIELDS[12:16]
BOOLEANS = ["shuffle", "skipped", "offline", "incognito_mode"]

DOC_NETWORKS = [
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
]
RECORDS_ERROR = "error: --records must be between 100 and 10000000"
DATA_ERROR = "error: refusing to write sample data into data/"
LISBON = ZoneInfo("Europe/Lisbon")


def run_generator(*args, cwd=REPO_ROOT):
    return subprocess.run(
        [sys.executable, str(GENERATOR), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def generate(out_dir, records=100, seed=42):
    result = run_generator("--records", str(records), "--seed", str(seed), "--out", str(out_dir))
    assert result.returncode == 0, result.stderr
    return out_dir


def load(out_dir):
    audio = json.loads((out_dir / AUDIO_FILE).read_text(encoding="utf-8"))
    video = json.loads((out_dir / VIDEO_FILE).read_text(encoding="utf-8"))
    return audio, video


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    out_dir = generate(tmp_path_factory.mktemp("sample"))
    audio, video = load(out_dir)
    return {"audio": audio, "video": video, "all": audio + video, "dir": out_dir}


def groups_filled(record):
    return [
        name
        for name, fields in (("music", MUSIC), ("podcast", PODCAST), ("audiobook", AUDIOBOOK))
        if any(record[f] is not None for f in fields)
    ]


def parse_ts(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def test_every_record_has_the_23_keys_in_order(dataset):
    assert len(FIELDS) == 23
    for record in dataset["all"]:
        assert list(record.keys()) == FIELDS


def test_total_records_matches_request(dataset):
    assert len(dataset["all"]) == 100


def test_exactly_one_descriptor_group_per_record(dataset):
    for record in dataset["all"]:
        assert len(groups_filled(record)) == 1, record


def test_content_types_are_split_across_files(dataset):
    assert {groups_filled(r)[0] for r in dataset["audio"]} == {"music", "audiobook"}
    assert {groups_filled(r)[0] for r in dataset["video"]} == {"podcast"}


def test_value_rules(dataset):
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    for record in dataset["all"]:
        assert type(record["ms_played"]) is int and record["ms_played"] > 0
        assert start <= parse_ts(record["ts"]) <= end
        assert record["offline_timestamp"] is None or type(record["offline_timestamp"]) is int
        assert re.fullmatch(r"[A-Z]{2}", record["conn_country"])
        for name in BOOLEANS:
            assert record[name] is None or isinstance(record[name], bool)


def test_ip_addresses_are_in_reserved_documentation_ranges(dataset):
    for record in dataset["all"]:
        address = ipaddress.ip_address(record["ip_addr"])
        assert any(address in network for network in DOC_NETWORKS), record["ip_addr"]


def test_uri_shapes(dataset):
    base62 = "[0-9A-Za-z]{22}"
    patterns = {
        "spotify_track_uri": rf"spotify:track:{base62}",
        "spotify_episode_uri": rf"spotify:episode:{base62}",
        "audiobook_uri": rf"spotify:show:{base62}",
        "audiobook_chapter_uri": rf"spotify:episode:{base62}",
    }
    for record in dataset["all"]:
        for field, pattern in patterns.items():
            if record[field] is not None:
                assert re.fullmatch(pattern, record[field]), (field, record[field])


def test_same_settings_give_byte_identical_files(tmp_path):
    first = generate(tmp_path / "a", records=150, seed=7)
    second = generate(tmp_path / "b", records=150, seed=7)
    for name in (AUDIO_FILE, VIDEO_FILE):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_different_seed_gives_different_content(tmp_path):
    first = generate(tmp_path / "a", seed=1)
    second = generate(tmp_path / "b", seed=2)
    assert (first / AUDIO_FILE).read_bytes() != (second / AUDIO_FILE).read_bytes()


def test_different_size_gives_different_dataset(tmp_path):
    small = generate(tmp_path / "a", records=100)
    large = generate(tmp_path / "b", records=300)
    audio, video = load(large)
    assert len(audio) + len(video) == 300
    assert (small / AUDIO_FILE).read_bytes() != (large / AUDIO_FILE).read_bytes()


def test_files_use_spotify_key_spacing(dataset):
    text = (dataset["dir"] / AUDIO_FILE).read_text(encoding="utf-8")
    assert '"ts" : "' in text


def test_null_booleans_present_at_minimum_size(dataset):
    for name in BOOLEANS:
        assert sum(1 for r in dataset["all"] if r[name] is None) >= 2, name


def test_private_sessions_present(dataset):
    assert sum(1 for r in dataset["all"] if r["incognito_mode"] is True) >= 3


def local_midnight_crossings(records):
    winter = summer = 0
    for record in records:
        end_utc = parse_ts(record["ts"])
        start_local = (end_utc.timestamp() - record["ms_played"] / 1000, LISBON)
        start = datetime.fromtimestamp(start_local[0], LISBON)
        end = end_utc.astimezone(LISBON)
        if start.date() != end.date():
            if end.utcoffset().total_seconds() == 0:
                winter += 1
            else:
                summer += 1
    return winter, summer


def test_streams_cross_local_midnight_in_winter_and_summer(dataset):
    winter, summer = local_midnight_crossings(dataset["all"])
    assert winter >= 2
    assert summer >= 2


def test_exact_duplicates_present(dataset):
    serialized = [json.dumps(r, sort_keys=True) for r in dataset["all"]]
    assert len(serialized) - len(set(serialized)) >= 3


def test_audiobook_streams_present(dataset):
    assert sum(1 for r in dataset["all"] if groups_filled(r) == ["audiobook"]) >= 3


@pytest.mark.parametrize("value", ["0", "99", "10000001", "-5", "abc"])
def test_invalid_records_are_rejected(value, tmp_path):
    result = run_generator("--records", value, "--out", str(tmp_path / "out"))
    assert result.returncode == 2
    assert RECORDS_ERROR in result.stderr
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("out", ["data", "data/sub", str(REPO_ROOT / "data"), str(REPO_ROOT / "data" / "sub")])
def test_writing_into_data_folder_is_refused(out):
    result = run_generator("--records", "100", "--out", out)
    assert result.returncode == 2
    assert DATA_ERROR in result.stderr
    assert not (REPO_ROOT / "data" / "sub").exists()
    assert not (REPO_ROOT / "data" / AUDIO_FILE).exists()


def test_unknown_option_exits_with_usage_error():
    result = run_generator("--nope")
    assert result.returncode == 2
