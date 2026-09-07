---
Task: t1725_1_abort_conflicted_pull_rebase_in_task_utils.md
Parent Task: aitasks/t1725_sync_deferrals_actionable_and_safe_to_continue.md
Sibling Tasks: aitasks/t1725/t1725_2_*.md, aitasks/t1725/t1725_3_*.md, aitasks/t1725/t1725_4_*.md, aitasks/t1725/t1725_5_*.md, aitasks/t1725/t1725_6_*.md
Archived Sibling Plans: aiplans/archived/p1725/p1725_*_*.md
Base branch: main
Output branch: main
---

# t1725_1 — abort a conflicted `pull --rebase` in `_task_pull_rebase`

Parent plan: `aiplans/p1725_sync_deferrals_actionable_and_safe_to_continue.md`,
section "Child 1". Finding 5 / AC3. No sibling dependency.

## Context

`_task_pull_rebase()` (`.aitask-scripts/lib/task_utils.sh` ~787) is a bare
`_ait_data_git pull --rebase --quiet`. `task_sync()` (~606; `aitask_pick_own.sh` at
every pick, `--sync`, the Step 7 ownership guard) and `task_push()`'s retry loop
(~745; `aitask_pick_own.sh:498`) both call it. On a conflict the rebase stays in
progress and every later `./ait git` write dies in `assert_data_worktree_clean`.
`aitask_sync.sh:do_pull_rebase` (~998) already aborts — this is the one framework
path that does not.

## Steps

1. `task_utils.sh`: `_data_wedge_state()` — echoes `rebase-merge` / `rebase-apply`
   found under `_ait_data_gitdir` (legacy fallback `git rev-parse --git-dir`), or
   nothing. Reuse in `assert_data_worktree_clean` only if the existing loop is
   identical; otherwise leave that loop alone. (t1725_2 reuses this helper; whichever
   lands first adds it — same name and contract.)
2. `_task_pull_rebase`: snapshot the wedge state before the pull. On failure:
   - no wedge before, wedge now → `_ait_data_git rebase --abort >/dev/null 2>&1 || true`;
     stderr: `aitask: rebase aborted after conflict - worktree restored, local commits kept`
   - wedge pre-existed → touch nothing; stderr: `aitask: a rebase is already in
     progress in the data worktree`
   Return the pull's exit status unchanged. (Callers capture `2>&1`, so the sentinel
   lands in `rebase_err` for the classifier.)
3. `_task_push_classify`: new arm **before** the CONFLICT arm — the pre-existing
   sentinel → `rebase_in_progress`. `rebase_conflict` keeps matching conflict text.
4. `_task_push_reason_hint`:
   - `rebase_conflict` → "rebase hit conflicts and was aborted (nothing left in
     progress); local and remote diverge — reconcile with 'ait syncer' or './ait sync'"
   - `rebase_in_progress` → "a rebase is already in progress in the data worktree;
     './ait git rebase --abort' discards only the partially replayed remote commits
     (your committed work stays on the branch), or resolve and './ait git rebase
     --continue'"
   - `assert_data_worktree_clean` die text: add the same "what --abort discards"
     sentence.
5. `aitask_crew_setmode.sh:125`, `aitask_crew_addwork.sh:328`: on the pull failure add
   `git rebase --abort 2>/dev/null || true` (crew worktrees are private).
6. `shellcheck .aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_crew_*.sh`.

## Verification

`tests/test_task_push.sh` (branch mode via `setup_branch_mode`; forced conflict =
the same line edited locally and via `advance_remote`'s second clone):
- `task_sync` → returns 0, `TASK_SYNC_STATUS=failed`, `TASK_SYNC_REASON=rebase_conflict`,
  no `rebase-merge` / `rebase-apply` in the data git-dir, and a subsequent
  `task_git commit` of a new file succeeds (AC3).
- the same through `task_push`'s retry loop.
- `aitask_pick_own.sh --sync` under the forced conflict → `SYNC_FAILED:rebase_conflict`,
  no wedge.
- negative control: a planted `rebase-merge` dir before the call is left in place,
  reason `rebase_in_progress`.
- both hint strings pinned verbatim.
Run `bash tests/test_task_push.sh`, `bash tests/test_task_git.sh`.

## Step 9

Standard post-implementation: commit on `main` (`bug: … (t1725_1)`), archive via the
workflow; parent t1725 archives after the last child.
