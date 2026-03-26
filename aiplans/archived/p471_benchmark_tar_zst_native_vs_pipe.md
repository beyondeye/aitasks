---
Task: t471_benchmark_tar_zst_native_vs_pipe.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Split the single `TarZstCLI` class in `bench_archive_formats.py` into two separate classes — `TarZstNative` (GNU tar `--zstd` flag) and `TarZstPipe` (`tar | zstd` pipe approach) — to benchmark them head-to-head.

## Files Modified

- `aidocs/benchmarks/bench_archive_formats.py` — Replaced `TarZstCLI` with `TarZstNative` and `TarZstPipe`. Fixed `Popen` bug where `capture_output=True` was incorrectly used (replaced with `stdout=PIPE, stderr=PIPE`). Updated format list builder to register both variants when capabilities exist.

## Probable User Intent

After creating follow-up task t470 (migrate tar.gz to tar.zst), the question arose whether to use GNU tar's native `--zstd` flag or the cross-platform pipe approach. This benchmark split was needed to make an informed decision. The results (pipe ~15% faster, identical output) resolved the open question in t470: use pipe universally.

## Final Implementation Notes

- **Actual work done:** Refactored `TarZstCLI` into `TarZstNative` and `TarZstPipe`, each as a standalone `ArchiveFormat` subclass. Fixed Popen `capture_output` bug in pipe class. Updated `main()` to register both when available.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed)
- **Issues encountered:** `subprocess.Popen` does not support `capture_output=True` (only `subprocess.run` does). Fixed by using `stdout=subprocess.PIPE, stderr=subprocess.PIPE` explicitly.
- **Key decisions:** Both variants produce identical archives (955KB). Pipe is faster due to parallel decompression in a separate process. This informed t470's decision to use pipe universally.
