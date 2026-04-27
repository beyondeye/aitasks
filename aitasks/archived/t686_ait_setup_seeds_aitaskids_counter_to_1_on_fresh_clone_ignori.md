---
priority: high
effort: medium
depends: []
issue_type: feature
status: Done
labels: [ait_setup]
assigned_to: dario-e@beyond-eye.com
issue: https://github.com/beyondeye/aitasks/issues/12
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-27 22:29
updated_at: 2026-04-27 23:27
completed_at: 2026-04-27 23:27
---

Issue created: 2026-04-27 22:15:17

## `ait setup` seeds `aitask-ids` counter to 1 on fresh clone, ignoring existing tasks on `aitask-data` branch

## Summary

On a fresh clone of a data-branch-mode repo where the `aitask-ids` counter
branch does not yet exist on the remote, `ait setup` initializes the
counter at `next_id=1` even when the `aitask-data` branch already contains
tasks with much higher IDs. The next `./ait create` will hand out IDs that
collide with existing tasks.

## Root cause

`ait setup` scans for the maximum existing task ID **before** it creates
the `.aitask-data/` worktree and the `aitasks/` symlink. At scan time the
local `aitasks/` directory is empty (or does not exist), so the scan
reports max = 0 and the counter is seeded with `next_id=1`. By the time
the symlinks expose the real tasks from the `aitask-data` branch, the
counter has already been pushed to the remote with the wrong value.

## Reproduction (observed 2026-04-27)

In a project with the `aitask-data` branch on the remote already
containing tasks up to `t10` (with subtasks `t10_1`..`t10_4`), and no
pre-existing `aitask-ids` branch on the remote:

1. `git clone <repo>`
2. `cd <repo> && ./ait setup`

Setup output includes:

    Max existing task ID: t0
    Initializing counter branch with next_id=1 (max + 1)
    Counter branch 'aitask-ids' created with next_id=1

After setup completes, the symlinks are in place and `ls aitasks/` shows
`t10*` task files. The counter on `origin/aitask-ids` is wrong.

## Suggested fix

Reorder `ait setup` so the data-branch worktree and symlinks are
established **before** the max-ID scan, OR have the scan look directly
inside the remote `aitask-data` tree (e.g. `git ls-tree origin/aitask-data
aitasks/`) when running on a fresh clone.

## Workaround

Manually push a corrected `next_id` to `aitask-ids` after setup, e.g.:

    git checkout aitask-ids
    echo 11 > next_id.txt
    git commit -am "Fix counter" && git push
    git checkout master
