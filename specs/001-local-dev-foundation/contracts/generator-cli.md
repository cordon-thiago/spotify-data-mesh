# Contract: sample data generator CLI

Interface exposed by `sample_data/generate.py`. Satisfies FR-007 to FR-011.

## Invocation

```text
python sample_data/generate.py [--records N] [--seed S] [--out DIR]
```

| Option | Default | Rule |
| --- | --- | --- |
| `--records` | `2000` | Integer, 100 to 10,000,000 inclusive |
| `--seed` | `42` | Any integer |
| `--out` | `sample_data` | Directory; created if missing. Must not be `data/` or inside it |

`make sample` runs the defaults; `make sample RECORDS=5000 SEED=7` passes options through.

## Output

Two files in `--out`, each a UTF-8 JSON array with Spotify's `"key" : value` spacing, one record per object, keys in the order of [data-model.md](../data-model.md):

- `streaming_history_audio_sample.json`: mostly music, some podcast episodes, all audiobook streams.
- `streaming_history_video_sample.json`: mostly podcast episodes, a little music.

Content type does not follow the file name, as in the real export (see `docs/real-export-findings.md`, updated in Phase 1).

Records are written one at a time, so memory use does not grow with `--records`. Existing files are overwritten.

## Behaviour guarantees

- Same `--records` and `--seed` give byte-identical files (same Python minor version).
- Different `--seed` or `--records` give a different dataset with the same schema.
- Every dataset contains all injected edge-case categories at any valid size.
- `ip_addr` values are always inside the RFC 5737 (IPv4) and RFC 3849 (`2001:db8::/32`, IPv6) documentation ranges.
- The program never reads, writes or lists `data/`.

## Exit codes and messages

| Code | When | Message (stderr) |
| --- | --- | --- |
| `0` | Success | stdout: one line per file with record count |
| `2` | `--records` outside 100 to 10,000,000, or not an integer | `error: --records must be between 100 and 10000000` |
| `2` | `--out` is `data/` or inside it | `error: refusing to write sample data into data/` |
| `2` | Unknown option | argparse usage message |

## Acceptance checks

Covered by `tests/test_generator.py`: schema and key order, one descriptor group per record, determinism across two runs, edge-case categories at the minimum size, IP range, URI shape, rejection of `--records 0`, `--records 99` and `--out data`.
