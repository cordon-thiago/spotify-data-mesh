"""Tests for ingest/inspect_export.py (no database needed)."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from generate import FIELDS
from inspect_export import EXPECTED_FIELDS

REPO_ROOT = Path(__file__).resolve().parents[1]
INSPECTOR = REPO_ROOT / "ingest" / "inspect_export.py"
GENERATOR = REPO_ROOT / "sample_data" / "generate.py"
AUDIO = "streaming_history_audio_sample.json"
VIDEO = "streaming_history_video_sample.json"


def inspect(folder, *extra):
    return subprocess.run(
        [sys.executable, str(INSPECTOR), str(folder), *extra], capture_output=True, text=True, cwd=REPO_ROOT
    )


@pytest.fixture
def sample_dir(tmp_path):
    out = tmp_path / "sample"
    subprocess.run(
        [sys.executable, str(GENERATOR), "--records", "100", "--out", str(out)], check=True, capture_output=True
    )
    return out


def records_of(folder, name):
    return json.loads((folder / name).read_text(encoding="utf-8"))


def file_section(output, name):
    """The part of the report that describes one file."""
    start = output.index(f"file: {name}")
    rest = output[start + 1 :]
    following = re.search(r"^file: ", rest, re.MULTILINE)
    return output[start : start + 1 + following.start()] if following else output[start:]


def key_line(section, key):
    line = next(l for l in section.splitlines() if l.split()[:1] == [key])
    present, types, nulls = line.split()[1:4]
    return int(present), types.split(","), int(nulls)


def test_expected_fields_match_the_generator():
    assert EXPECTED_FIELDS == FIELDS


def test_lists_each_file_with_its_record_count_and_size(sample_dir):
    result = inspect(sample_dir)
    assert result.returncode == 0, result.stderr
    for name in (AUDIO, VIDEO):
        count = len(records_of(sample_dir, name))
        assert re.search(rf"file: {re.escape(name)}\s+\(\d+\.\d+ MB, {count} records\)", result.stdout)


def test_reports_key_counts_json_types_and_nulls(sample_dir):
    result = inspect(sample_dir)
    section = file_section(result.stdout, AUDIO)
    records = records_of(sample_dir, AUDIO)
    for key in ("shuffle", "incognito_mode"):
        present, types, nulls = key_line(section, key)
        assert present == len(records)
        assert types == ["boolean", "null"]
        assert nulls == sum(1 for r in records if r[key] is None)
    present, types, nulls = key_line(section, "ms_played")
    assert (present, types, nulls) == (len(records), ["number"], 0)


def test_counts_records_per_content_group(sample_dir):
    result = inspect(sample_dir)
    for name in (AUDIO, VIDEO):
        records = records_of(sample_dir, name)
        music = sum(1 for r in records if r["spotify_track_uri"] is not None)
        podcast = sum(1 for r in records if r["spotify_episode_uri"] is not None)
        audiobook = sum(1 for r in records if r["audiobook_uri"] is not None)
        expected = f"content: music {music}, podcast {podcast}, audiobook {audiobook}, none 0, several 0"
        assert expected in file_section(result.stdout, name)
        assert music + podcast + audiobook == len(records)


def test_flags_keys_outside_the_sample_schema_and_keys_present_in_some_records(sample_dir):
    path = sample_dir / AUDIO
    records = records_of(sample_dir, AUDIO)
    records[0]["brand_new_field"] = "x"
    path.write_text(json.dumps(records), encoding="utf-8")
    section = file_section(inspect(sample_dir).stdout, AUDIO)
    assert "outside the 23 sample fields: brand_new_field" in section
    present, _, _ = key_line(section, "brand_new_field")
    assert present == 1 < len(records)


def test_flags_sample_fields_that_are_absent_everywhere(sample_dir):
    for name in (AUDIO, VIDEO):
        records = records_of(sample_dir, name)
        for record in records:
            record.pop("ip_addr")
        (sample_dir / name).write_text(json.dumps(records), encoding="utf-8")
    section = file_section(inspect(sample_dir).stdout, AUDIO)
    assert "absent sample fields: ip_addr" in section


def test_non_matching_files_are_listed_as_ignored(sample_dir):
    (sample_dir / "README.md").write_text("notes", encoding="utf-8")
    assert "ignored: README.md" in inspect(sample_dir).stdout


def test_summary_totals(sample_dir):
    output = inspect(sample_dir).stdout
    assert "TOTAL: 2 files, 100 records" in output


def test_output_contains_no_values(sample_dir):
    output = inspect(sample_dir).stdout
    assert "Synthetic" not in output
    assert not re.search(r"(192\.0\.2|198\.51\.100|203\.0\.113)\.\d+", output)
    assert "spotify:" not in output


def test_malformed_file_exits_with_code_2_and_no_content(sample_dir):
    (sample_dir / "streaming_history_zz_broken.json").write_text('[{"ts": "SECRETMARKER9"', encoding="utf-8")
    result = inspect(sample_dir)
    assert result.returncode == 2
    assert "error: invalid JSON in streaming_history_zz_broken.json at line 1, column" in result.stderr
    assert "SECRETMARKER9" not in result.stdout + result.stderr


def test_no_matching_files_exits_with_code_2(tmp_path):
    result = inspect(tmp_path)
    assert result.returncode == 2
    assert "error: no files matching streaming_history_*.json found in" in result.stderr
