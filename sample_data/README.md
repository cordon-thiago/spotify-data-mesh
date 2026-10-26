# sample_data

Synthetic streaming history with the same 23-field schema as the real Spotify export. **Everything here is made up**: names are `Synthetic ...`, URIs are random, and IP addresses come only from the reserved documentation ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`). It is safe to commit and serves as the test fixture for the whole pipeline.

## Files

| File | Content |
| --- | --- |
| `streaming_history_audio_sample.json` | Music and audiobook streams |
| `streaming_history_video_sample.json` | Podcast episodes |
| `generate.py` | The generator that writes both files |

The split mirrors the owner's real samples, where episodes appear in the "video" file. Real file names and which file holds which content type are confirmed against the real ZIP in Phase 1.

## Regenerate

```bash
make sample                       # 2000 records, seed 42 (the committed files)
make sample RECORDS=5000 SEED=7   # a different dataset, same schema
```

The same `RECORDS` and `SEED` always produce byte-identical files. `RECORDS` must be between 100 and 10,000,000. The generator streams records to disk, so memory stays flat (about 17 MB for a million records). Run `make sample` with the defaults afterwards to restore the committed files.

## Edge cases always present

Whatever the size, every dataset contains:

- `null` in each of `shuffle`, `skipped`, `offline` and `incognito_mode`
- private sessions (`incognito_mode = true`)
- streams that cross midnight in `Europe/Lisbon`, in winter and in summer
- exact duplicate records
- audiobook streams
- a music artist and a podcast show with the same name (`Synthetic Artist 07`)

Records are not sorted by time.
