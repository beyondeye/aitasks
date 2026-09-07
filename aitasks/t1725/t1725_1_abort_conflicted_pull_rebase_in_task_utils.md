---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-09-07 16:37
updated_at: 2026-09-07 16:37
---

## Context

Parent t1725 (sync deferrals actionable and safe to continue), finding 5 /
acceptance criterion 3. Every framework path that runs `git pull --rebase` on the
task-data worktree must either resolve or **abort** on conflict — never leave
`rebase-merge` behind for the next writer to trip over.

The batch sync (`aitask_sync.sh:do_pull_rebase`) already aborts (t1676). The one
framework path that does not is `_task_pull_rebase()` in
`.aitask-scripts/lib/task_utils.sh` (~787): a bare `_ait_data_git pull --rebase
--quiet`. It is shared by `task_sync()` (~606 — run by `aitask_pick_own.sh` at every
pick, in `--sync` mode, and by the Step 7 ownership guard) and by `task_push()`'s
retry loop (~745 — run after every claim, `aitask_pick_own.sh:498`). On 2026-09-07,
one second after t1717 committed `plan_approved`, that path hit a trivial
frontmatter conflict, stopped mid-rebase with 13 picks remaining, and from then on
every `./ait git` write in that agent died at `assert_data_worktree_clean`
("stuck mid-rebase-merge"); the agent then fell back to plain git on `main`.

## Key files

- `.aitask-scripts/lib/task_utils.sh` — `_task_pull_rebase` (~787), `task_sync`
  (~606), `task_push` (~745), `_task_push_classify` (~828),
  `_task_push_reason_hint` (~865), `assert_data_worktree_clean` (~291),
  `_ait_data_gitdir` (~176), `AIT_GIT_INPROGRESS_STATES`
- `.aitask-scripts/aitask_crew_setmode.sh:125`, `.aitask-scripts/aitask_crew_addwork.sh:328`
  — the same bare `git pull --rebase --quiet 2>/dev/null || true` on crew worktrees
- `tests/test_task_push.sh` — existing fixture (`setup_remote_and_clone`,
  `advance_remote`, `setup_branch_mode`, `reload_task_utils`)

## Reference files for patterns

- `aitask_sync.sh:do_pull_rebase` (~998) — the abort-on-conflict shape already used
  by the batch sync (`task_git rebase --abort 2>/dev/null || true`)
- `aitask_sync.sh:_worktree_wedged` (~331) — the git-dir sentinel scan; this task
  adds the shared `_data_wedge_state` helper in `task_utils.sh` that both the guard
  and the pull can use (child t1725_2 reuses it — whichever lands first adds it)
- `tests/test_task_git.sh` ~868 — planting `rebase-merge` in the data git-dir

## Implementation plan

1. `task_utils.sh`: add `_data_wedge_state()` — echoes `rebase-merge` /
   `rebase-apply` (first hit from `AIT_GIT_INPROGRESS_STATES`, or just the two rebase
   states) for the data git-dir via `_ait_data_gitdir`, falling back to
   `git rev-parse --git-dir` in legacy mode; echoes nothing when clean. Reuse it in
   `assert_data_worktree_clean` only if the loop there is identical; otherwise leave
   that loop alone.
2. `_task_pull_rebase`: snapshot `_data_wedge_state` **before** the pull. On failure:
   - no wedge before, wedge now → `_ait_data_git rebase --abort >/dev/null 2>&1 ||
     true`, print `aitask: rebase aborted after conflict - worktree restored, local
     commits kept` to **stderr** (callers capture `2>&1`, so it lands in
     `rebase_err`);
   - wedge pre-existed → touch nothing, print `aitask: a rebase is already in
     progress in the data worktree` to stderr.
   Return the pull's exit status unchanged in both cases.
3. `_task_push_classify`: new arm **before** the CONFLICT arm, matching the
   pre-existing sentinel → `rebase_in_progress`. `rebase_conflict` keeps matching
   the conflict text.
4. `_task_push_reason_hint`:
   - `rebase_conflict` → "rebase hit conflicts and was aborted (nothing left in
     progress); local and remote diverge — reconcile with 'ait syncer' or './ait sync'"
   - `rebase_in_progress` → "a rebase is already in progress in the data worktree;
     './ait git rebase --abort' discards only the partially replayed remote commits
     (your committed work stays on the branch), or resolve and './ait git rebase
     --continue'"
   - `assert_data_worktree_clean`'s die text gains the same one-line "what --abort
     discards" sentence.
5. Crew scripts: on the two `git pull --rebase --quiet` failures add
   `git rebase --abort 2>/dev/null || true` (crew worktrees are private — no
   pre-existing-wedge check needed).
6. `shellcheck .aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_crew_*.sh`.

## Verification

Extend `tests/test_task_push.sh` (branch mode via `setup_branch_mode`; a forced
conflict = the same line edited locally and remotely):
- `task_sync` under the forced conflict → returns 0, `TASK_SYNC_STATUS=failed`,
  `TASK_SYNC_REASON=rebase_conflict`, **no** `rebase-merge` / `rebase-apply` under
  the data git-dir, and a subsequent `task_git commit` of a new file succeeds
  (AC3: "the task's next `./ait git commit` succeeds").
- the same through `task_push`'s retry loop.
- end-to-end AC3: `aitask_pick_own.sh --sync` under the forced conflict prints
  `SYNC_FAILED:rebase_conflict` and leaves no wedge.
- **negative control:** a *planted* `rebase-merge` directory before the call is left
  in place, reason `rebase_in_progress` — proves the abort only undoes its own rebase.
- hint text pinned verbatim for both reasons (the guard's message is part of the
  guard).
Run: `bash tests/test_task_push.sh`, `bash tests/test_task_git.sh`.
