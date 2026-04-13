---
Task: t533_archive_script_overbroad_git_add.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Narrow `git add -u` scope in `aitask_archive.sh` (t533)

## Context

`aitask_archive.sh` currently uses broad `git add -u "$TASK_DIR/" "$PLAN_DIR/"`
commands that sweep in **every** modified-or-deleted tracked file under
`aitasks/` and `aiplans/`. The intent is to record the deletion of the original
task/plan files after they are moved to `archived/` with `mv`, but the actual
scope is the entire tree.

This silently contaminates archival commits with unrelated in-progress edits
made by sibling agents on the shared `aitask-data` branch. The incident log
(2026-04-13, commit `30b738dc`) shows agent B's archival commit for t447_5
sweeping in agent A's mid-edit of `t461_2` and `p461_2`.

The fix must be on the script side: the `aitask-data` branch is intentionally
shared between agents, so the archive script needs to be side-effect-free with
respect to unrelated files.

## Target files

- `.aitask-scripts/aitask_archive.sh` — lines 233, 487–489 (the three broad
  `git add -u` calls, plus the in-function structure for archive_child)
- `tests/test_archive_no_overbroad_add.sh` — **new** regression test
- `CLAUDE.md` — add new test to the Testing section list

## Approach

Apply **Option A** from the task description — replace the broad `git add -u
<dir>/` calls with narrow `git add -u <specific_file>` calls targeting exactly
the paths that were moved or modified.

### Why Option A, not Option B (`git mv`)

Option A is the minimal, surgical fix that matches the current control flow:
`archive_move()` uses plain `mv`, and the variables `$task_file`,
`$plan_file`, `$child_task_file`, `$child_plan_file`, `$parent_task_file` all
continue to hold the **original** (pre-move) paths. Passing them to
`git add -u` stages the deletion exactly as intended. Option B would require
refactoring `archive_move()` to call `task_git mv` instead of `mv`, which is a
larger change with wider test impact and gains nothing for this bug.

### How `git add -u <path>` behaves (for reviewers)

- If `<path>` is a tracked file that still exists → stages the modification
- If `<path>` is a tracked file that no longer exists → stages the deletion
- If `<path>` is a directory → stages **every** modified/deleted tracked file
  under it (this is the bug we're fixing)

Both the "modification" and "deletion" semantics are needed by this script:
the `parent_task_file` in `archive_child()` is modified in-place by
`--remove-child`, and after the move it is deleted. A single narrowed
`task_git add -u "$parent_task_file"` correctly handles both cases.

## Changes

### 1. `archive_parent()` — replace line 233

Current:
```bash
task_git add -u "$TASK_DIR/" "$PLAN_DIR/" 2>/dev/null || true
```

Replace with:
```bash
# Stage deletion of original task/plan paths (files already moved by archive_move)
task_git add -u "$task_file" 2>/dev/null || true
if [[ -n "$plan_file" ]]; then
    task_git add -u "$plan_file" 2>/dev/null || true
fi
```

Both `$task_file` and `$plan_file` already hold the original paths (set on
lines 175 and 180 before `archive_move` runs).

### 2. `archive_child()` — restructure parent-plan resolution + replace lines 487–489

**Structural change (at top of function, alongside existing parent resolution):**

Declare `parent_plan_file` and `parent_plan_basename` as function-scoped
locals with empty defaults. They will be populated inside the
`parent_archived` branch when the parent plan is moved.

```bash
local parent_plan_file=""
local parent_plan_basename=""
```

**Inside the `if [[ -z "$remaining_children" ]]` block (around lines 462–469):**

Remove the inner `local parent_plan_file` declaration — we want the
function-scoped one so the commit section can see it.

**Replace lines 487–489:**

Current:
```bash
task_git add -u "$TASK_DIR/t${parent_num}/" 2>/dev/null || true
task_git add -u "$PLAN_DIR/p${parent_num}/" 2>/dev/null || true
task_git add -u "$TASK_DIR/" "$PLAN_DIR/" 2>/dev/null || true
```

Replace with:
```bash
# Stage deletion of original child task/plan paths
task_git add -u "$child_task_file" 2>/dev/null || true
if [[ -n "${child_plan_file:-}" ]]; then
    task_git add -u "$child_plan_file" 2>/dev/null || true
fi
# Stage parent task file: in-place modification from --remove-child, or deletion if parent was archived
task_git add -u "$parent_task_file" 2>/dev/null || true
```

**Simplify the parent_archived commit block (lines 492–501):**

Drop the redundant `local parent_plan_file` re-declaration and
`resolve_plan_file` re-call. Use the function-scoped variables we already
populated. Also stage the deletion of the original parent plan path.

```bash
if [[ "$parent_archived" == true ]]; then
    task_git add "$ARCHIVED_DIR/$parent_task_basename" 2>/dev/null || true
    if [[ -n "$parent_plan_basename" ]]; then
        task_git add "$ARCHIVED_PLAN_DIR/$parent_plan_basename" 2>/dev/null || true
        task_git add -u "$parent_plan_file" 2>/dev/null || true
    fi
fi
```

### 3. New regression test: `tests/test_archive_no_overbroad_add.sh`

Model structure on `tests/test_archive_related_issues.sh` (setup_archive_project
helper, isolated bare-remote + local clone, assert_eq/assert_contains helpers).

**Case A — parent archival:**
1. Create `aitasks/t100_target.md` + `aiplans/p100_target.md` and
   `aitasks/t101_bystander.md` + `aiplans/p101_bystander.md`.
2. Commit all four.
3. Modify `aitasks/t101_bystander.md` (unstaged).
4. Run `aitask_archive.sh 100`.
5. Parse `COMMITTED:<hash>`; run `git show --name-only <hash>`.
6. Assert commit list contains t100 archived paths, does NOT contain any t101/p101 path.
7. Assert t101_bystander remains modified-but-unstaged.

**Case B — child archival:**
1. Parent with `children_to_implement: [t200_1, t200_2]`, plus child task + plan files.
2. Modify `aitasks/t200/t200_2_bystander.md` (unstaged).
3. Run `aitask_archive.sh 200_1`.
4. Assert commit contains t200_1 archive paths + parent update (children_to_implement
   edit), but NOT t200_2.
5. Assert t200_2 remains modified-but-unstaged.

**Case C — parent auto-archival:**
1. Parent with single `children_to_implement: [t300_1]`. Separate unrelated
   `aitasks/t301_bystander.md`.
2. Modify t301 (unstaged).
3. Run `aitask_archive.sh 300_1`.
4. Assert commit contains t300_1 and t300 parent archive paths but NOT t301.

### 4. Update `CLAUDE.md` Testing section

Add `bash tests/test_archive_no_overbroad_add.sh` to the test list.

## Verification

1. `shellcheck .aitask-scripts/aitask_archive.sh` — no new findings.
2. `bash tests/test_archive_related_issues.sh` — still passes.
3. `bash tests/test_archive_folded.sh` — still passes.
4. `bash tests/test_archive_utils.sh` — still passes.
5. `bash tests/test_archive_scan.sh` — still passes.
6. `bash tests/test_archive_no_overbroad_add.sh` — new regression test passes.
7. Manual smoke test in the live repo: modify a second unrelated task file,
   archive a test task, confirm `git show --name-only HEAD` contains only the
   first task's files.

## Step 9 (Post-Implementation)

Standard post-implementation cleanup per task-workflow Step 9:
- User review and approval of changes (Step 8)
- Code commit with `bug:` prefix and `(t533)` suffix
- Plan file commit via `./ait git`
- Archive task via `./.aitask-scripts/aitask_archive.sh 533`
- Push via `./ait git push`

## Final Implementation Notes

- **Actual work done:** Applied Option A exactly as planned.
  - `archive_parent()`: replaced the broad `task_git add -u "$TASK_DIR/" "$PLAN_DIR/"`
    with two narrow `task_git add -u "$task_file"` / `"$plan_file"` calls.
  - `archive_child()`: promoted `parent_plan_file` and `parent_plan_basename` to
    function-scoped locals (with empty defaults) so the commit section can see
    the original pre-move path. The inner block inside
    `if [[ -z "$remaining_children" ]]` now assigns the function-scoped vars
    directly (no shadowing `local`).
  - Replaced the three overbroad `add -u` calls at the start of the commit
    section with narrow `add -u` on `$child_task_file`, `$child_plan_file`, and
    `$parent_task_file` (which handles both the in-place parent modification from
    `--remove-child` and the post-move deletion when parent is auto-archived).
  - Simplified the `parent_archived` commit block to use the pre-populated
    `parent_plan_file` / `parent_plan_basename` and also stage the deletion of
    the original parent plan path.
- **New regression test:** `tests/test_archive_no_overbroad_add.sh` covers parent
  archival, child archival without auto-archival, and child archival with parent
  auto-archival. Each case creates a bystander task/plan, modifies it unstaged,
  runs the archive script, and asserts (a) the bystander paths are NOT in the
  archival commit and (b) the bystander files remain modified-but-unstaged
  afterwards. 22/22 assertions pass on the fixed script; 12 fail on the
  pre-fix script (verified via `git stash` round-trip).
- **Deviations from plan:** None material. Test uses
  `git show --name-status -M0 --pretty=format:` so rename detection is disabled
  and delete+add lines appear separately — this was a test-setup detail not
  spelled out in the plan but necessary for the "deletion staged" assertions
  to match.
- **Issues encountered:**
  - `test_archive_related_issues.sh` and `test_archive_folded.sh` were found to
    be pre-broken on main (their `setup_archive_project` helpers don't copy
    `lib/archive_utils.sh` and `lib/agentcrew_utils.sh`, which `task_utils.sh`
    and `aitask_archive.sh` now source). The new test copies both. A follow-up
    aitask should fix the older tests' helpers.
- **Key decisions:**
  - Kept `$parent_plan_file` as a plain string holding the original path instead
    of pre-computing before any moves. This keeps the code flow linear
    (resolve in the archive block, consume in the commit block).
  - Narrow comments explain *why* we narrow (sibling agent contamination) so
    future drift back to broad `add -u` is less likely.
