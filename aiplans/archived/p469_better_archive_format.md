---
Task: t469_better_archive_format.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Archive Format Benchmark (t469)

## Context

The aitasks project stores archived task/plan markdown files in tar.gz bundles (`_b0/old0.tar.gz` through `old4.tar.gz`). The main pain point: `tar -tzf` (listing files) requires decompressing the entire archive in RAM, even though the numbered archive system provides O(1) lookup to know WHICH archive a file should be in. We need benchmarks to evaluate alternative formats.

## Approach

Create a single Python benchmark script at `aidocs/benchmarks/bench_archive_formats.py` that:
1. Extracts files from existing `old*.tar.gz` archives as test data
2. Re-archives them in each candidate format
3. Benchmarks 5 key operations with warmup + multiple repetitions
4. Reports results in a formatted table

## Formats to Benchmark

| Format | Python API | CLI | Why |
|--------|-----------|-----|-----|
| tar (uncompressed) | `tarfile` | - | Baseline — isolate compression overhead |
| tar.gz | `tarfile` | `tar -czf/-tzf/-xzf` | Current format (baseline) |
| tar.zst | pipe via subprocess | `tar --zstd` or pipe `zstd` | Faster decompression than gzip |
| tar.xz | `tarfile` | - | Better compression ratio, slower |
| zip | `zipfile` | `zip`/`unzip` | Central directory = O(1) file listing |

Both Python stdlib and CLI variants where applicable (project uses both in production).

## Operations to Benchmark

1. **List all files** — The main bottleneck. zip should win dramatically (reads central directory only).
2. **Check if specific file exists** — Production use: verify a file is in the archive.
3. **Extract single file** — Production use: read a specific archived task/plan.
4. **Create archive** — Production use: `aitask_zip_old.sh` creates bundles.
5. **Archive size** — Compression ratio for markdown files.

## Implementation

- `aidocs/benchmarks/bench_archive_formats.py` — Benchmark script (~500 lines)
- `aidocs/benchmarks/archive_format_results.md` — Results table and recommendations

## Final Implementation Notes

- **Actual work done:** Created `aidocs/benchmarks/bench_archive_formats.py` (benchmark script, ~500 lines) and `aidocs/benchmarks/archive_format_results.md` (results + analysis). Benchmarks 7 format variants (tar, tar.gz Python/CLI, tar.zst CLI, tar.xz, zip Python/CLI) across 4 operations + archive sizes.
- **Deviations from plan:** Moved from `benchmarks/` to `aidocs/benchmarks/` per user request. Added results markdown file with full tables and recommendations. Had to fix tar member name normalization (`./` prefix mismatch between CLI-created and Python-created archives).
- **Issues encountered:** `tarfile.extractfile()` failed when member names had `./` prefix from CLI tar creation. Fixed by adding `_normalize_tar_name()` helper and robust member lookup in `TarPython.extract_single()`.
- **Key decisions:** Used both Python stdlib and CLI subprocess variants since the project uses both in production. Used `time.perf_counter_ns()` for nanosecond precision. Graceful degradation for missing tools (zstd, zip CLI).
