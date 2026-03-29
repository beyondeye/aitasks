---
priority: high
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [task-archive, archiveformat]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-27 13:10
updated_at: 2026-03-29 10:39
completed_at: 2026-03-29 10:39
---

Migrate the Python archive iteration module (archive_iter.py) from tarfile with r:gz mode to subprocess pipe approach using zstd. Update corresponding tests.

## Context

This task is fully independent of the bash migration tasks (t470_1, t470_2, t470_3) and can run in parallel. The Python tarfile module does not natively support zstd, so subprocess pipes are required.

## Key Files to Modify

### `.aitask-scripts/lib/archive_iter.py`

**`archive_path_for_id()` (line 23):**
- Change `f"_b{dir_num}/old{bundle}.tar.gz"` → `f"_b{dir_num}/old{bundle}.tar.zst"`

**`iter_numbered_archives()` (lines 26-32):**
- Change glob `old*.tar.gz` → `old*.tar.zst`
- Add fallback: also glob `old*.tar.gz` for backward compat (repos not yet migrated)
- Deduplicate: if both `.tar.zst` and `.tar.gz` exist for same bundle, prefer `.tar.zst`

**`iter_legacy_archive()` (lines 35-39):**
- Try `old.tar.zst` first, fall back to `old.tar.gz`

**`_iter_single_archive()` (lines 104-118):**
- Replace `tarfile.open(archive_path, "r:gz")` with format-aware approach:
  - For `.tar.zst`: `subprocess.Popen(["zstd", "-dc", str(archive_path)], stdout=subprocess.PIPE)` then `tarfile.open(fileobj=proc.stdout, mode="r|")` (streaming tar read)
  - For `.tar.gz`: keep `tarfile.open(archive_path, "r:gz")` (native, no subprocess needed)
- Auto-detect by file extension: `archive_path.suffix == ".zst"` or check `archive_path.name.endswith(".tar.zst")`
- Ensure subprocess is properly cleaned up (proc.wait(), handle SIGPIPE)

**`_is_child_filename()` (line 99):** No change needed (pure regex).

### `tests/test_archive_iter_consolidated.py` (19 test cases)

**`_make_tar_gz()` helper (lines 30-38):**
- Rename to `_make_archive()` (or keep old name as alias)
- For `.tar.zst` archives: create tar in memory, then compress via subprocess:
  ```python
  import subprocess, io, tarfile
  buf = io.BytesIO()
  with tarfile.open(fileobj=buf, mode="w") as tf:
      for name, content in files.items():
          data = content.encode("utf-8")
          info = tarfile.TarInfo(name=name)
          info.size = len(data)
          tf.addfile(info, io.BytesIO(data))
  buf.seek(0)
  proc = subprocess.run(["zstd", "-q", "-o", str(archive_path)], input=buf.read(), check=True)
  ```
- Update all test calls to create `.tar.zst` instead of `.tar.gz`
- Add backward compat test: create `.tar.gz` and verify `_iter_single_archive` can still read it

**Test paths to update:**
- All `old*.tar.gz` → `old*.tar.zst` in test fixture creation
- `_b0/old0.tar.gz` → `_b0/old0.tar.zst` path assertions
- `old.tar.gz` → `old.tar.zst` legacy path assertions

### `tests/test_aitask_stats_py.py`
- Lines 150-153: `tar_path = tar_dir / "old0.tar.gz"` → `"old0.tar.zst"`
- Update archive creation to use zstd compression

## Reference Files
- Current `archive_iter.py` (119 lines) — small, self-contained module
- Python `tarfile` docs: `mode="r|"` is streaming read (no seeking, compatible with pipe)
- Python `subprocess.Popen` for pipe management

## Implementation Plan
1. Update `archive_path_for_id()` extension
2. Update glob patterns in `iter_numbered_archives()` and `iter_legacy_archive()` with fallback
3. Rewrite `_iter_single_archive()` with format-aware dispatch
4. Update test helper `_make_tar_gz()` → `_make_archive()` for `.tar.zst` creation
5. Update all 19 test cases
6. Update `test_aitask_stats_py.py`
7. Run tests: `python3 -m pytest tests/test_archive_iter_consolidated.py tests/test_aitask_stats_py.py -v`

## Verification
- `python3 -m pytest tests/test_archive_iter_consolidated.py -v` — all 19 tests pass
- `python3 -m pytest tests/test_aitask_stats_py.py -v` — passes
- Verify `zstd` is available: `which zstd`
