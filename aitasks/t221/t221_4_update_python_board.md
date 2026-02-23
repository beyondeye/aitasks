---
priority: medium
effort: medium
depends: [t221_1]
issue_type: refactor
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-23 11:15
updated_at: 2026-02-23 12:38
---

## Context

This is child task 4 of t221 (Move aitasks/aiplans to separate branch). The parent task implements a symlink + worktree architecture where task/plan data lives on an orphan `aitask-data` branch. This child task updates the Python TUI board (`aiscripts/board/aitask_board.py`) to be worktree-aware for all git operations.

The board reads task files from `aitasks/` (which works unchanged via symlinks), but its git operations (status check, commit, delete, revert) currently use `subprocess.run(["git", ...])` which targets the main branch. In branch mode, these must target the `.aitask-data/` worktree instead.

## Key Files to Modify

1. **`aiscripts/board/aitask_board.py`** — All git subprocess calls

## Reference Files for Patterns

- `aiscripts/board/aitask_board.py`:
  - Line 26-28: `TASKS_DIR = Path("aitasks")`, `METADATA_FILE`, `TASK_TYPES_FILE`
  - Lines 301-320: `refresh_git_status()` — git status check
  - Lines 1357-1370: Git checkout (revert task)
  - Lines 2478-2530: `_execute_delete()` — git rm + commit
  - Lines 2535-2559: `_git_commit_tasks()` — git add + commit

## Implementation Plan

### Step 1: Add worktree detection helper

Add a module-level constant or helper near the top of the file (after the existing `TASKS_DIR` definition):

```python
# Detect if task data lives in a separate worktree
DATA_WORKTREE = Path(".aitask-data")

def _task_git_cmd() -> list[str]:
    """Return git command prefix for task data operations.
    In branch mode: ["git", "-C", ".aitask-data"]
    In legacy mode: ["git"]
    """
    if DATA_WORKTREE.exists() and (DATA_WORKTREE / ".git").exists():
        return ["git", "-C", str(DATA_WORKTREE)]
    return ["git"]
```

### Step 2: Update refresh_git_status() (line 301)

```python
# Before:
result = subprocess.run(
    ["git", "status", "--porcelain", "--", "aitasks/"],
    ...
)
# After:
result = subprocess.run(
    [*_task_git_cmd(), "status", "--porcelain", "--", "aitasks/"],
    ...
)
```

### Step 3: Update revert operation (line 1359)

```python
# Before:
result = subprocess.run(
    ["git", "checkout", "--", str(self.task_data.filepath)],
    ...
)
# After:
result = subprocess.run(
    [*_task_git_cmd(), "checkout", "--", str(self.task_data.filepath)],
    ...
)
```

### Step 4: Update _execute_delete() (line 2493)

```python
# Before:
result = subprocess.run(
    ["git", "rm", "-f", str(path)],
    ...
)
# ...
result = subprocess.run(
    ["git", "commit", "-m", f"ait: Delete task {task_num} and associated files"],
    ...
)
# After: use _task_git_cmd() prefix for both operations
```

### Step 5: Update _git_commit_tasks() (line 2539)

```python
# Before:
subprocess.run(["git", "add", str(task.filepath)], ...)
result = subprocess.run(["git", "commit", "-m", message], ...)
# After: use _task_git_cmd() prefix for both operations
```

### Important Notes

- `TASKS_DIR = Path("aitasks")` does NOT need changing — symlinks handle file reads
- `METADATA_FILE` and `TASK_TYPES_FILE` paths don't need changing — symlinks handle reads
- Only `subprocess.run(["git", ...])` calls that operate on task/plan files need updating
- The `subprocess.Popen` calls for launching external processes (claude, editor) do NOT need changing

## Verification Steps

1. **Legacy mode:** Run `ait board` without `.aitask-data/` — all git operations work as before
2. **Branch mode:** Set up worktree, run `ait board`:
   - Verify git status indicators show correctly
   - Verify commit action works (stages + commits to data branch)
   - Verify delete action works (git rm + commit on data branch)
   - Verify revert action works (checkout from data branch)
3. **Test `_task_git_cmd()` detection:** Verify it returns correct prefix in both modes
