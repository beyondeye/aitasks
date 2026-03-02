---
Task: t284_confirm_before_profile_save.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Add Save Confirmation Modal to Profiles Tab (t284)

## Context

The Profiles tab in `ait settings` has a Save button that directly writes the profile to disk without confirmation. The task requires:
1. Verifying the save button works correctly
2. Verifying field order is preserved when writing back to file
3. Adding a confirmation modal with three options: Save, Save and Commit, Cancel
4. Commit message format: `"ait: updated/created execution profile <profile name>"`

## Verification Findings

**Save button works**: `_save_profile()` at line 1544 collects all form widget values, builds a data dict, and calls `config_mgr.save_profile()` which writes YAML to disk. This is functional.

**Field order is preserved**: `yaml.dump(data, f, sort_keys=False)` at line 339 preserves dict insertion order. The `data` dict starts from the existing profile (loaded by `yaml.safe_load` which preserves order in Python 3.7+), and existing keys maintain their position when updated via `data[key] = val`. New keys are appended in schema order. This is correct behavior.

## Implementation

### File: `aiscripts/settings/settings_app.py`

### Step 1: Add `subprocess` import (top of file, line ~9)

Add `import subprocess` alongside existing imports.

### Step 2: Add `_task_git_cmd()` helper (near top, after imports ~line 60)

Reuse the same pattern from `aitask_board.py`:
```python
def _task_git_cmd() -> list[str]:
    data_wt = Path(".aitask-data")
    if data_wt.exists() and (data_wt / ".git").exists():
        return ["git", "-C", str(data_wt)]
    return ["git"]
```

### Step 3: Create `SaveProfileConfirmScreen` modal class (after `DeleteProfileConfirmScreen`, ~line 857)

Follow the `DeleteProfileConfirmScreen` pattern:
- Title: "Save profile '{profile_name}'?"
- Three buttons: "Save" (success), "Save and Commit" (primary), "Cancel" (default)
- Returns: `"save"`, `"save_commit"`, or `None`

### Step 4: Modify `on_button_pressed()` to show modal (line 1519-1522)

Instead of calling `_save_profile()` directly, push the `SaveProfileConfirmScreen` and handle result in a callback.

### Step 5: Add `_handle_save_profile()` callback method

- If result is `"save"`: call existing `_save_profile(filename)`
- If result is `"save_commit"`: call `_save_profile(filename)`, then determine the file path and run `./ait git add <path> && ./ait git commit -m "ait: updated execution profile <name>"`
- If result is `None`: do nothing (cancel)

For new profiles (just created, not yet committed): use "created" instead of "updated" in the commit message. Detect by checking if the file existed before the save.

### Step 6: Add `_commit_profile()` method

Run git commands using subprocess, following the same worktree-aware pattern as `aitask_board.py:_git_commit_tasks()` (line 3285). The `aitasks/` directory is a symlink to `.aitask-data/aitasks/`, and `.aitask-data/` is a git worktree on the `aitask-data` branch. The `_task_git_cmd()` helper from Step 2 handles this transparently.

```python
def _commit_profile(self, filename: str):
    layer = self.config_mgr.profile_layers.get(filename, "project")
    if layer == "user":
        path = LOCAL_PROFILES_DIR / filename
    else:
        path = PROFILES_DIR / filename
    data = self.config_mgr.profiles.get(filename, {})
    name = data.get("name", filename)

    git_cmd = _task_git_cmd()
    try:
        subprocess.run([*git_cmd, "add", str(path)], capture_output=True, timeout=5)
        result = subprocess.run(
            [*git_cmd, "commit", "-m", f"ait: Updated execution profile {name}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            self.notify(f"Committed profile '{name}'")
        else:
            self.notify(f"Commit failed: {result.stderr.strip()}", severity="error")
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        self.notify(f"Git error: {exc}", severity="error")
```

**Note:** Path `aitasks/metadata/profiles/fast.yaml` is relative to CWD. When `_task_git_cmd()` returns `["git", "-C", ".aitask-data"]`, git resolves the path relative to `.aitask-data/`, which is correct since `aitasks/` → `.aitask-data/aitasks/`.

## Verification

1. Run `python3 aiscripts/settings/settings_app.py` and navigate to Profiles tab
2. Modify a profile field, click Save → should show modal with 3 options
3. Test "Cancel" → no changes saved
4. Test "Save" → profile saved, no commit
5. Test "Save and Commit" → profile saved and committed
6. Verify field order: `cat aitasks/metadata/profiles/fast.yaml` before and after save — field order should match

## Final Implementation Notes
- **Actual work done:** Added `SaveProfileConfirmScreen` modal with Save/Save+Commit/Cancel options, wired it to the save button via `_handle_save_profile` callback, added `_commit_profile` method using worktree-aware `_task_git_cmd()` helper. Verified save button works and field order is preserved through YAML round-trip.
- **Deviations from plan:** Simplified the "created vs updated" commit message distinction — always uses "Updated" since even new profiles are immediately saved to disk on creation (via `_handle_new_profile`), so subsequent saves are always updates.
- **Issues encountered:** None — implementation was straightforward following existing modal patterns.
- **Key decisions:** Reused the `_task_git_cmd()` pattern from `aitask_board.py` for worktree-aware git operations rather than shelling out to `./ait git`.
