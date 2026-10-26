"""Unit tests for the helpers in ingest/load.py (no database needed)."""

import re
from types import SimpleNamespace

import pytest

from load import (
    BOOLEAN_FIELDS,
    IngestError,
    check_keys,
    compare_counts,
    filter_db_error,
    find_files,
    read_records,
    render,
)


def touch(root, relative, content="[]"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# --- find_files -------------------------------------------------------------


def test_find_files_matches_case_insensitively_and_recursively(tmp_path):
    touch(tmp_path, "b/streaming_history_video_sample.json")
    touch(tmp_path, "a/Streaming_History_Audio_2024.json")
    touch(tmp_path, "sub/dir/STREAMING_HISTORY_X.JSON")
    touch(tmp_path, "README.md", "text")
    touch(tmp_path, "other.json")
    matched, ignored = find_files(tmp_path, "streaming_history_*.json")
    assert matched == [
        "a/Streaming_History_Audio_2024.json",
        "b/streaming_history_video_sample.json",
        "sub/dir/STREAMING_HISTORY_X.JSON",
    ]
    assert ignored == ["README.md", "other.json"]


def test_find_files_honours_a_custom_pattern(tmp_path):
    touch(tmp_path, "Streaming_History_Audio_2024.json")
    touch(tmp_path, "Streaming_History_Video_2024.json")
    matched, ignored = find_files(tmp_path, "*audio*.json")
    assert matched == ["Streaming_History_Audio_2024.json"]
    assert ignored == ["Streaming_History_Video_2024.json"]


def test_find_files_returns_nothing_for_an_empty_folder(tmp_path):
    assert find_files(tmp_path, "streaming_history_*.json") == ([], [])


# --- read_records -----------------------------------------------------------


def test_read_records_returns_the_list(tmp_path):
    path = touch(tmp_path, "f.json", '[{"a": 1}, {"a": null}]')
    assert read_records(path, "f.json") == [{"a": 1}, {"a": None}]


def test_read_records_accepts_an_empty_array(tmp_path):
    assert read_records(touch(tmp_path, "f.json", "[]"), "f.json") == []


def test_read_records_tolerates_a_byte_order_mark(tmp_path):
    path = tmp_path / "f.json"
    path.write_bytes(b"\xef\xbb\xbf" + b'[{"a": 1}]')
    assert read_records(path, "f.json") == [{"a": 1}]


def test_read_records_reports_invalid_json_without_content(tmp_path):
    path = touch(tmp_path, "f.json", '[{"secret": "SECRETMARKER"}')
    with pytest.raises(IngestError) as error:
        read_records(path, "f.json")
    assert error.value.code == 2
    assert re.fullmatch(r"error: invalid JSON in f\.json at line \d+, column \d+", error.value.message)
    assert "SECRETMARKER" not in error.value.message


@pytest.mark.parametrize("content", ['{"a": 1}', "[1, 2]", '"text"', "7", '[{"a": 1}, 3]'])
def test_read_records_rejects_anything_but_an_array_of_objects(tmp_path, content):
    path = touch(tmp_path, "f.json", content)
    with pytest.raises(IngestError) as error:
        read_records(path, "f.json")
    assert error.value.code == 2
    assert error.value.message == "error: f.json is not an array of records"


# --- render -----------------------------------------------------------------


def test_render_keeps_null_distinct_from_empty_string():
    assert render(None) is None
    assert render("") == ""


@pytest.mark.parametrize(
    "value, expected",
    [(True, "true"), (False, "false"), (5, "5"), (0, "0"), (1.5, "1.5"), ("abc", "abc")],
)
def test_render_gives_source_faithful_text(value, expected):
    assert render(value) == expected


def test_render_keeps_nested_values_as_json_text():
    assert render({"a": [1, None]}) == '{"a": [1, null]}'


# --- check_keys -------------------------------------------------------------


def test_check_keys_passes_when_keys_equal_the_data_columns():
    check_keys({"b": 1, "a": 2}, ["a", "b"], "f.json")


def test_check_keys_reports_an_unknown_key():
    with pytest.raises(IngestError) as error:
        check_keys({"a": 1, "b": 2, "extra": 3}, ["a", "b"], "f.json")
    assert error.value.code == 2
    assert error.value.message == "error: unknown key extra in f.json"


def test_check_keys_reports_a_missing_key():
    with pytest.raises(IngestError) as error:
        check_keys({"a": 1}, ["a", "b"], "f.json")
    assert error.value.code == 2
    assert error.value.message == "error: missing key b in f.json"


# --- filter_db_error --------------------------------------------------------


class InvalidTextRepresentation(Exception):
    """Stand-in for a psycopg server error: carries a SQLSTATE and a diagnostic context."""

    def __init__(self, context):
        super().__init__('invalid input syntax for type integer: "SECRETVALUE"')
        self.sqlstate = "22P02"
        self.diag = SimpleNamespace(
            context=context,
            message_primary='invalid input syntax for type integer: "SECRETVALUE"',
        )


def test_filter_db_error_names_file_class_state_line_and_column_but_not_the_value():
    error = InvalidTextRepresentation('COPY t, line 7, column ms_played: "SECRETVALUE"')
    text = filter_db_error(error, "f.json")
    assert text == "error: database error in f.json: InvalidTextRepresentation (SQLSTATE 22P02), line 7, column ms_played"
    assert "SECRETVALUE" not in text


def test_filter_db_error_never_reads_line_or_column_from_the_quoted_value():
    error = InvalidTextRepresentation('COPY t, line 3: "x line 9, column leaked"')
    text = filter_db_error(error, "f.json")
    assert text.endswith("(SQLSTATE 22P02), line 3")
    assert "leaked" not in text


def test_filter_db_error_works_without_a_context():
    text = filter_db_error(InvalidTextRepresentation(None), "f.json")
    assert text == "error: database error in f.json: InvalidTextRepresentation (SQLSTATE 22P02)"


# --- compare_counts ---------------------------------------------------------


def counts(rows, **nulls):
    return {"rows": rows, "nulls": {field: nulls.get(field, 0) for field in BOOLEAN_FIELDS}}


def test_compare_counts_passes_when_everything_matches():
    side = {"a.json": counts(10, shuffle=2), "b.json": counts(5, skipped=1)}
    compare_counts(side, {name: dict(value) for name, value in side.items()})


def test_compare_counts_fails_on_a_row_difference():
    with pytest.raises(IngestError) as error:
        compare_counts({"a.json": counts(10)}, {"a.json": counts(9)})
    assert error.value.code == 1
    assert error.value.message == "error: counts differ, load rolled back"


@pytest.mark.parametrize("field", BOOLEAN_FIELDS)
def test_compare_counts_fails_on_a_null_difference_in_any_boolean(field):
    with pytest.raises(IngestError) as error:
        compare_counts({"a.json": counts(10, **{field: 2})}, {"a.json": counts(10, **{field: 1})})
    assert error.value.code == 1


def test_compare_counts_fails_when_a_file_is_missing_on_one_side():
    with pytest.raises(IngestError) as error:
        compare_counts({"a.json": counts(1), "b.json": counts(1)}, {"a.json": counts(1)})
    assert error.value.code == 1
