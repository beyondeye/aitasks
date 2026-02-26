---
priority: medium
effort: medium
depends: [t258_2]
issue_type: bug
status: Ready
labels: [codebrowser]
created_at: 2026-02-26 15:02
updated_at: 2026-02-26 15:02
---

## Context

The codebrowser's `explain_manager.py` has a bug in `_find_run_dir()` where the glob pattern `{dir_key}__*` incorrectly matches subdirectory keys (e.g., `aiscripts__*` matches `aiscripts__board__*`). Additionally, since the extract script now handles directory naming (t258_2), the Python-side rename logic should be removed. Finally, a cleanup-at-startup mechanism should be added.

## Task

Update `aiscripts/codebrowser/explain_manager.py` to:
1. Fix the `_find_run_dir()` glob bug
2. Remove the post-hoc rename logic from `generate_explain_data()`
3. Remove the `_find_newest_timestamp_dir()` method
4. Add a `cleanup_stale_runs()` method
5. Call cleanup at TUI startup

## Key Files to Modify

- `aiscripts/codebrowser/explain_manager.py` — all changes in this file

## Implementation Details

**1. Fix `_find_run_dir()` (line 38):**
Change glob from `f"{dir_key}__*"` to `f"{dir_key}__[0-9]*"` — timestamps always start with a digit, which distinguishes them from sub-keys.

**2. Update `generate_explain_data()` (lines 83-108):**
- Pass `--source-key` to the extract script subprocess call:
```python
dir_key = self._dir_to_key(rel_dir)
subprocess.run(
    [EXTRACT_SCRIPT, "--gather", "--source-key", dir_key] + direct_files,
    env=env, check=True, capture_output=True,
    cwd=str(self._root),
)
```
- Remove lines 92-102 (the rename logic + `_find_newest_timestamp_dir()` call)
- Instead, find the run dir using `_find_run_dir(dir_key)`:
```python
run_dir = self._find_run_dir(dir_key)
if run_dir is None:
    return {}
ref_yaml = run_dir / "reference.yaml"
```

**3. Remove `_find_newest_timestamp_dir()` (lines 110-127):** Delete entirely — no longer needed.

**4. Add `cleanup_stale_runs()` method:**
```python
def cleanup_stale_runs(self) -> int:
    """Remove stale run directories, keeping only the newest per dir_key."""
    if not self._cb_dir.exists():
        return 0
    groups: dict[str, list[Path]] = {}
    for entry in self._cb_dir.iterdir():
        if not entry.is_dir():
            continue
        name = entry.name
        # Parse <key>__<YYYYMMDD_HHMMSS>
        if "__" in name:
            last_sep = name.rfind("__")
            ts_part = name[last_sep + 2:]
            if len(ts_part) == 15 and ts_part[8] == "_" and ts_part.replace("_", "").isdigit():
                key = name[:last_sep]
                groups.setdefault(key, []).append(entry)
                continue
        # Bare timestamp
        if len(name) == 15 and name[8] == "_" and name.replace("_", "").isdigit():
            groups.setdefault("_bare_timestamp_", []).append(entry)
    removed = 0
    for key, dirs in groups.items():
        if len(dirs) <= 1:
            continue
        dirs.sort(key=lambda p: p.name)
        for stale_dir in dirs[:-1]:
            shutil.rmtree(stale_dir)
            removed += 1
    return removed
```

**5. Call in `__init__()` (line 27):**
```python
self.cleanup_stale_runs()
```

## Verification

1. Start codebrowser TUI — verify stale dirs cleaned up at startup
2. Browse to a file, verify explain data loads correctly
3. Press `r` to refresh — verify new data generated correctly
4. Check that `aiscripts` and `aiscripts__board` are separate keys (no cross-matching)
