---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [skills, procedures]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-23 19:21
updated_at: 2026-03-23 19:22
---

# Fix task-creation-batch.md git log command for branch mode

## Problem

The `task-creation-batch.md` procedure recommends using plain `git log` to extract the task ID after creation:

```bash
git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'
```

In branch mode (where task data lives on the `aitask-data` branch in `.aitask-data/` worktree), this queries the **main branch** — not the `aitask-data` branch where the task was actually committed. This returns the wrong result or nothing at all.

Verified behavior:
- `git log -1 --name-only` → shows last commit on main (e.g., `.aitask-scripts/brainstorm/brainstorm_app.py`)
- `git -C .aitask-data log -1 --name-only` → shows last task commit (e.g., `aitasks/t428/t428_5_...md`)

## Root cause

The procedure was written before branch mode existed, or wasn't updated when branch mode was introduced. The `git log` command doesn't go through `./ait git` which handles worktree routing.

## Fix

In `.claude/skills/task-workflow/task-creation-batch.md`, change the Output section's git command from:

```bash
git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'
```

to:

```bash
./ait git log -1 --name-only --pretty=format:'' | grep '^aitasks/t'
```

`./ait git` routes through `task_git()` which automatically uses `git -C .aitask-data` in branch mode and plain `git` in legacy mode.

## Additional context (transient git add error)

During an `/aitask-explore` session, `aitask_create.sh --batch --commit` failed twice with:
```
The following paths are ignored by one of your .gitignore files:
aitasks
```
then succeeded on the third attempt with no changes. This indicates `task_git add` transiently ran against the main worktree (where `aitasks/` is in `.gitignore`) instead of `.aitask-data` (where it's not). The transient failure could not be reproduced — `_ait_detect_data_worktree()` and `task_git` work correctly in current state. This may indicate a race condition or temporary worktree inconsistency under concurrent access. Worth monitoring but no fix identified.

## Also check

- Search all skill files and procedures for bare `git log` or `git diff` commands that should use `./ait git` instead — the same bug pattern may exist elsewhere.
