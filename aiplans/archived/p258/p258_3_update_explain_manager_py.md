---
Task: t258_3_update_explain_manager_py.md
Parent Task: aitasks/t258_automatic_clean_up_of_aiexplains_for_code_browser.md
Sibling Tasks: aitasks/t258/t258_1_*.md, aitasks/t258/t258_2_*.md, aitasks/t258/t258_4_*.md, aitasks/t258/t258_5_*.md
Archived Sibling Plans: aiplans/archived/p258/p258_1_*.md, aiplans/archived/p258/p258_2_*.md
Worktree: (none — working on current branch)
Branch: (current)
Base branch: main
---

## Plan: Update `explain_manager.py`

### Step 1: Fix `_find_run_dir()` glob bug

**File:** `aiscripts/codebrowser/explain_manager.py`, line 38

Change:
```python
pattern = str(self._cb_dir / f"{dir_key}__*")
```
To:
```python
pattern = str(self._cb_dir / f"{dir_key}__[0-9]*")
```

This prevents `aiscripts__*` from matching `aiscripts__board__*`. Timestamps always start with a digit.

### Step 2: Update `generate_explain_data()`

**Lines 83-108:** Modify the subprocess call to pass `--source-key`:

```python
dir_key = self._dir_to_key(rel_dir)
env = os.environ.copy()
env["AIEXPLAINS_DIR"] = CODEBROWSER_DIR
subprocess.run(
    [EXTRACT_SCRIPT, "--gather", "--source-key", dir_key] + direct_files,
    env=env, check=True, capture_output=True,
    cwd=str(self._root),
)
```

**Remove lines 92-102** (the post-hoc rename logic involving `_find_newest_timestamp_dir`).

Replace with:
```python
run_dir = self._find_run_dir(dir_key)
if run_dir is None:
    return {}

ref_yaml = run_dir / "reference.yaml"
if not ref_yaml.exists():
    return {}

return self.parse_reference_yaml(ref_yaml)
```

### Step 3: Remove `_find_newest_timestamp_dir()`

Delete the entire method (lines 110-127). It's no longer needed since the shell script handles naming.

### Step 4: Add `cleanup_stale_runs()` method

Add after `_find_run_dir()`:

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

### Step 5: Call cleanup in `__init__()`

Add after `os.makedirs(self._cb_dir, exist_ok=True)`:
```python
self.cleanup_stale_runs()
```

### Step 6: Verify

1. Start codebrowser TUI — check stale dirs cleaned up at startup
2. Browse a file — verify explain data loads correctly
3. Press `r` to refresh — verify data regenerated correctly
4. Verify `aiscripts` and `aiscripts__board` are separate keys

### Step 9: Post-Implementation

Archive task following the standard workflow.

## Final Implementation Notes

- **Actual work done:** All 5 planned changes implemented exactly as specified: (1) fixed `_find_run_dir()` glob from `{dir_key}__*` to `{dir_key}__[0-9]*`, (2) updated `generate_explain_data()` to pass `--source-key` and use `_find_run_dir()` instead of rename logic, (3) removed `_find_newest_timestamp_dir()` entirely, (4) added `cleanup_stale_runs()` method, (5) added cleanup call in `__init__()`.
- **Deviations from plan:** None — implementation matched the plan exactly. The `cleanup_stale_runs()` method was placed where `_find_newest_timestamp_dir()` used to be (between `generate_explain_data()` and `parse_reference_yaml()`), which is a natural location.
- **Issues encountered:** None. All line numbers and code references in the plan were accurate against the current codebase.
- **Key decisions:** The `dir_key` computation was moved before the subprocess call in `generate_explain_data()` since it's now needed as the `--source-key` argument. The old code computed it after the subprocess call.
- **Notes for sibling tasks:** The Python-side rename logic is now fully removed — the extract script (modified in t258_2) handles all directory naming via `--source-key`. The `cleanup_stale_runs()` method in Python mirrors the logic in `aitask_explain_cleanup.sh` (from t258_1) but is scoped to `aiexplains/codebrowser/` only. The glob fix `[0-9]*` is important for any code that does key-based lookups in the codebrowser directory — keys with `__` separators (like `aiscripts__board`) are now properly isolated from their prefixes.
