---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts, task-archive, git-integration]
created_at: 2026-04-13 13:46
updated_at: 2026-04-13 13:46
---

## Bug

`aitask_archive.sh` uses an over-broad `git add -u` that sweeps in unrelated, in-progress task/plan edits made by sibling agents working on the shared `aitask-data` branch.

The offending lines are in `.aitask-scripts/aitask_archive.sh`:

- `archive_parent()` line 233:
  ```bash
  task_git add -u "$TASK_DIR/" "$PLAN_DIR/" 2>/dev/null || true
  ```
- `archive_child()` line 489:
  ```bash
  task_git add -u "$TASK_DIR/" "$PLAN_DIR/" 2>/dev/null || true
  ```

`git add -u <dir>/` stages **every** modified-or-deleted tracked file under the entire `aitasks/` and `aiplans/` trees. The intent is to record the deletion of the *original* task/plan paths after they were moved to `archived/` with `mv`, but the scope is the whole tree.

## Observed incident (2026-04-13)

While I (agent A) was mid-edit on `aitasks/t461/t461_2_crew_setmode_cli.md` and had just rewritten `aiplans/p461/p461_2_crew_setmode_cli.md`, agent B ran `aitask_archive.sh 447_5`. Agent B's broad `git add -u` swept up agent A's modifications. Commit `30b738dc` ("ait: Archive completed t447_5 and parent t447 task and plan files") therefore contained:

- The actual t447_5 + t447 archival files (expected)
- `aiplans/p461/p461_2_crew_setmode_cli.md` (unrelated — agent A's plan rewrite)
- `aitasks/t461/t461_2_crew_setmode_cli.md` (unrelated — agent A's status edit)

The contamination is silent: the commit message lies about its scope, but the data still lands on the right branch, so nothing visibly breaks. Any in-progress task/plan edit by a sibling agent will keep getting swallowed into the next archival commit until this is fixed.

## Why both agents were on the same branch

The `aitask-data` branch is intentionally **shared** between agents. Per-agent worktrees on it would defeat its purpose as a single source of truth for task state (locks, status transitions, archival). The fix must therefore be on the script side, not the workflow side.

## Proposed fix

Replace the broad `git add -u "$TASK_DIR/" "$PLAN_DIR/"` with targeted updates scoped to the specific files being archived. Two viable approaches:

### Option A — narrow `git add -u` to specific paths

```bash
# archive_parent()
task_git add -u "$task_file" 2>/dev/null || true
[[ -n "$plan_file" ]] && task_git add -u "$plan_file" 2>/dev/null || true
```

```bash
# archive_child()
task_git add -u "$child_task_file" 2>/dev/null || true
[[ -n "$child_plan_file" ]] && task_git add -u "$child_plan_file" 2>/dev/null || true
# When parent is also archived
if [[ "$parent_archived" == true ]]; then
    task_git add -u "$parent_task_file" 2>/dev/null || true
    [[ -n "${parent_plan_file:-}" ]] && task_git add -u "$parent_plan_file" 2>/dev/null || true
fi
```

This preserves the current intent (record the deletion of the moved file) but limits the scope.

### Option B — replace `mv` + `add -u` with `git mv`

Use `task_git mv "$src" "$dest_dir/"` in `archive_move()` instead of `mkdir -p && mv`. Git natively records the rename in one operation, eliminating the need for any subsequent `git add -u` to pick up the deletion. This is a slightly bigger refactor but is the cleanest fix.

The `--remove-child` invocation on the parent task file in `archive_child()` separately modifies the parent file in place — that modification still needs to be staged explicitly (e.g., `task_git add -u "$parent_task_file"`) regardless of which option is chosen.

**Recommendation:** Option A is the minimal, surgical fix. Option B is cleaner but touches more lines.

## Regression test

Add to `tests/` (or extend an existing archive test):

1. Set up an isolated git repo with two task files and two plan files (`t100`, `t101`).
2. Modify `aitasks/t101_*.md` (e.g., flip status to Implementing) but **do not** stage or commit it.
3. Run `aitask_archive.sh 100`.
4. Assert that the resulting commit contains **only** files belonging to t100 (`git show --name-only HEAD` must not list any t101 path).
5. Assert that `aitasks/t101_*.md` still shows as modified-but-unstaged afterward.

This regression test would have caught the incident, and will catch any future drift back to a broad `add -u`.

## Verification

1. `shellcheck .aitask-scripts/aitask_archive.sh` — no new findings.
2. `bash tests/test_archive_*.sh` — existing archive tests still pass.
3. New regression test passes.
4. Manual: with two terminals on the same repo, edit a task file in one, run `ait` to archive a different task in the other, confirm the archival commit does not contain the in-progress edit.

## Notes

- Lines 233 and 489 of `.aitask-scripts/aitask_archive.sh` are the exact spots; both must be fixed.
- Do not also stage the in-progress sibling work as a "bonus" — the archive script must be idempotent and side-effect-free with respect to unrelated files.
