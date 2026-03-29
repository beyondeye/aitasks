---
Task: t470_4_python_archive_iter_migration.md
Parent Task: aitasks/t470_migrate_archive_format_tar_gz_to_tar_zst.md
Sibling Tasks: aitasks/t470/t470_1_*.md, aitasks/t470/t470_5_*.md
Archived Sibling Plans: aiplans/archived/p470/p470_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# t470_4: Python archive_iter.py Migration

## Overview
Migrate the Python archive iteration module from `tarfile.open(path, "r:gz")` to subprocess-based zstd decompression with streaming tar read. Fully independent of bash changes.

## Step 1: Update archive_path_for_id()

```python
# Before:
return archived_dir / f"_b{dir_num}/old{bundle}.tar.gz"
# After:
return archived_dir / f"_b{dir_num}/old{bundle}.tar.zst"
```

## Step 2: Update iter_numbered_archives()

```python
def iter_numbered_archives(archived_dir: Path):
    # Primary: .tar.zst
    zst_archives = sorted(archived_dir.glob("_b*/old*.tar.zst"))
    # Fallback: .tar.gz (only those without a .tar.zst counterpart)
    gz_archives = sorted(archived_dir.glob("_b*/old*.tar.gz"))

    seen_stems = set()
    for archive in zst_archives:
        seen_stems.add(archive.with_suffix("").with_suffix(""))  # strip .tar.zst
        yield from _iter_single_archive(archive)
    for archive in gz_archives:
        stem = archive.with_suffix("").with_suffix("")  # strip .tar.gz
        if stem not in seen_stems:
            yield from _iter_single_archive(archive)
```

## Step 3: Update iter_legacy_archive()

```python
def iter_legacy_archive(archived_dir: Path):
    zst_path = archived_dir / "old.tar.zst"
    gz_path = archived_dir / "old.tar.gz"
    if zst_path.exists():
        yield from _iter_single_archive(zst_path)
    elif gz_path.exists():
        yield from _iter_single_archive(gz_path)
```

## Step 4: Rewrite _iter_single_archive()

Format-aware dispatch based on file extension:

```python
import subprocess

def _iter_single_archive(archive_path: Path):
    try:
        if archive_path.name.endswith(".tar.zst"):
            # Pipe: zstd -dc | tar streaming read
            proc = subprocess.Popen(
                ["zstd", "-dc", str(archive_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            try:
                with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
                    for member in tf:
                        if member.isfile() and member.name.endswith(".md"):
                            f = tf.extractfile(member)
                            if f is not None:
                                text = f.read().decode("utf-8", errors="replace")
                                yield (Path(member.name).name, text)
            finally:
                proc.stdout.close()
                proc.wait()
        else:
            # Native tarfile for .tar.gz
            with tarfile.open(archive_path, "r:gz") as tf:
                for member in tf:
                    if member.isfile() and member.name.endswith(".md"):
                        f = tf.extractfile(member)
                        if f is not None:
                            text = f.read().decode("utf-8", errors="replace")
                            yield (Path(member.name).name, text)
    except (tarfile.TarError, OSError, subprocess.SubprocessError):
        return
```

## Step 5: Update test helper in test_archive_iter_consolidated.py

```python
def _make_archive(archive_path: Path, files: dict[str, str]) -> None:
    """Create a tar.zst archive."""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    buf.seek(0)
    subprocess.run(
        ["zstd", "-q", "-o", str(archive_path)],
        input=buf.read(), check=True
    )

def _make_tar_gz(archive_path: Path, files: dict[str, str]) -> None:
    """Create a tar.gz archive (for backward compat tests)."""
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tf:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
```

## Step 6: Update all test cases

- Replace `_make_tar_gz()` calls with `_make_archive()` for .tar.zst paths
- Update archive path strings: `old0.tar.gz` → `old0.tar.zst`, etc.
- Add backward compat test: create `.tar.gz`, verify `_iter_single_archive` reads it

## Step 7: Update test_aitask_stats_py.py

- Lines 150-153: change `old0.tar.gz` → `old0.tar.zst`
- Update archive creation to use zstd compression

## Step 8: Verify

```bash
python3 -m pytest tests/test_archive_iter_consolidated.py -v
python3 -m pytest tests/test_aitask_stats_py.py -v
```

## Step 9 Reference
Post-implementation: user review, commit, archive task, push.

## Final Implementation Notes
- **Actual work done:** Implemented all 8 plan steps. Updated `archive_path_for_id()` to return `.tar.zst`. Rewrote `iter_numbered_archives()` with dual-glob dedup (.tar.zst preferred over .tar.gz). Updated `iter_legacy_archive()` with .tar.zst-first fallback. Rewrote `_iter_single_archive()` with format-aware dispatch: subprocess zstd pipe with streaming `tarfile.open(mode="r|")` for .tar.zst, native `tarfile.open(mode="r:gz")` for .tar.gz backward compat. Added `_make_archive()` test helper for .tar.zst creation and 2 new tests (backward compat + dedup preference). Updated `test_aitask_stats_py.py` archive fixture.
- **Deviations from plan:** (1) Added `-f` flag to `zstd` in test helper `_make_archive()` for overwrite safety (learned from t470_3). (2) Used `os.path.basename()` consistently (matching existing code style) instead of `Path(member.name).name` as shown in plan. (3) Total tests 18 (not 19 as stated in task description — the task file overcounted; added 2 new tests for 18 total).
- **Issues encountered:** `pytest` not installed — used `python3 -m unittest` runner instead. All tests pass.
- **Key decisions:** Used streaming tar mode `"r|"` for zstd pipe (no seeking, compatible with pipe input). Kept native `tarfile.open("r:gz")` for .tar.gz backward compat (no subprocess needed).
- **Notes for sibling tasks:**
  - Python archive iteration now supports both .tar.zst (primary) and .tar.gz (backward compat) seamlessly.
  - Test helper `_make_archive()` creates .tar.zst archives using subprocess pipe; `_make_tar_gz()` kept for backward compat test fixtures.
  - `subprocess` import added to both archive_iter.py and test files.
  - `zstd -f` flag is important for overwrite safety in test helpers (confirmed from t470_3 experience).
