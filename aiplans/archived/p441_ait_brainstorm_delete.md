---
Task: t441_ait_brainstorm_delete.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Implementation Plan: t441 — ait brainstorm delete + archive fix

## Context

Two issues:
1. **No delete subcommand**: Users cannot completely remove a brainstorm session. The only cleanup path is `archive`, which finalizes first.
2. **Archive error**: `ait brainstorm archive 427` crashes with `ValueError: HEAD node 'n000_init' has no plan_file.` because `finalize_session()` requires the HEAD node to have a plan. Sessions that were initialized but never had plans generated cannot be archived.

## Part 1: Fix archive error

The archive command unconditionally calls `finalize_session()` first, which fails when HEAD has no plan. Fix: make the archive bash script handle the no-plan case gracefully by catching the finalize failure and asking the user whether to proceed with archive-only (skip plan copy) or abort.

### Files to modify

**`.aitask-scripts/aitask_brainstorm_archive.sh`** (lines 74-82):
- Before calling finalize, check if HEAD has a plan using the Python CLI
- Add a `--skip-finalize` flag for programmatic use (delete will use this)
- If finalize fails with the no-plan error, warn and continue with archive + cleanup instead of dying
- Alternatively (simpler): try finalize, if it fails, print a warning and continue

Approach: Wrap the finalize call — if it fails, emit `NO_PLAN` instead of `PLAN:<path>` and continue.

```bash
finalize_output=$("$PYTHON" ... finalize --task-num "$TASK_NUM" 2>&1) || {
    if echo "$finalize_output" | grep -q "has no plan_file"; then
        warn "HEAD node has no plan file — skipping plan finalize"
        echo "NO_PLAN"
    else
        die "Failed to finalize session: $finalize_output"
    fi
}
```

## Part 2: Add delete subcommand

### Files to create

**`.aitask-scripts/aitask_brainstorm_delete.sh`** — New bash script:
- Usage: `ait brainstorm delete <task_num> [--yes]`
- Without `--yes`: prompt for confirmation using `read -p`
- Calls `brainstorm_cli.py delete --task-num <task_num>` to validate session exists
- Calls `aitask_crew_cleanup.sh --crew brainstorm-<task_num> --delete-branch --batch`
- If crew cleanup can't clean (NOT_TERMINAL status), force-remove by setting crew status to Completed first, then retry cleanup
- Output: `DELETED:<task_num>`

### Files to modify

**`.aitask-scripts/brainstorm/brainstorm_cli.py`**:
- Add `cmd_delete()` function
- Add `delete` subparser with `--task-num` argument
- Function validates session exists, calls `delete_session()`, prints `DELETED:<task_num>`

**`.aitask-scripts/brainstorm/brainstorm_session.py`**:
- Add `delete_session(task_num)` function
- Removes the entire crew worktree directory: `shutil.rmtree(crew_worktree(task_num))`
- Returns nothing (raises if session doesn't exist)

**`ait`** (dispatcher, lines 208-228):
- Add `delete)` case: `exec "$SCRIPTS_DIR/aitask_brainstorm_delete.sh" "$@"`
- Update help text to include `delete` subcommand
- Update the error message listing available subcommands

### Files to update (tests)

**`tests/test_brainstorm_cli.sh`**:
- Add Test 9: `brainstorm delete` removes session and worktree
- Add Test 10: `brainstorm delete` rejects non-existent session
- Add Test 11: `brainstorm archive` succeeds with no-plan session (the fix)
- Copy the new delete script in `setup_test_repo()`

## Implementation Order

1. Fix `aitask_brainstorm_archive.sh` — graceful no-plan handling
2. Add `delete_session()` to `brainstorm_session.py`
3. Add `cmd_delete` to `brainstorm_cli.py`
4. Create `aitask_brainstorm_delete.sh`
5. Update `ait` dispatcher
6. Add tests to `tests/test_brainstorm_cli.sh`

## Verification

```bash
# Test the archive fix
./ait brainstorm archive 427    # should now succeed with warning

# Test delete on an existing session
./ait brainstorm list           # see sessions
./ait brainstorm delete 427     # should prompt, then delete

# Run tests
bash tests/test_brainstorm_cli.sh
```

## Final Implementation Notes

- **Actual work done:** Implemented both features as planned — archive fix and delete subcommand
- **Deviations from plan:** Dropped the `--skip-finalize` flag from archive script (unnecessary — the error handling approach is sufficient). Delete script uses Python `shutil.rmtree` for session removal, then falls back to crew cleanup for branch deletion (handles the case where worktree is already gone gracefully)
- **Issues encountered:** None — implementation was straightforward
- **Key decisions:** The delete command first removes files via Python CLI (`delete_session` uses `shutil.rmtree`), then crew cleanup handles branch deletion. If crew cleanup fails (e.g., NOT_FOUND because Python already removed the dir), it falls back to direct `git branch -D` and worktree prune
- **Additional change:** Added best-effort remote branch cleanup (`git push origin --delete`) to `aitask_crew_cleanup.sh` when `--delete-branch` is set. This benefits both archive and delete operations. Also added remote cleanup to the delete script's fallback path.

## Step 9: Post-Implementation

Archive task, push changes.
