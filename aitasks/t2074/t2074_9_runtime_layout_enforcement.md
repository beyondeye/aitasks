---
priority: high
effort: high
depends: [t2074_3, t2074_4, t2074_5, t2074_6, t2074_7, t2074_8, 2064]
issue_type: refactor
status: Ready
labels: [framework, git, data_integrity, bash_scripts, task-workflow]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:33
updated_at: 2026-10-20 12:34
---

## Context

This is the core flip of t2074 (remove legacy repository mode). After it lands,
no layout other than the data branch with its data worktree is supported. The
binding contract is **C0 (command-requirement table), C2 (enforcement),
C3 (errexit audit), C5 (front door), C6 (no silent migration)** and the
"Probe definition" in `aiplans/p2074_remove_legacy_repository_mode_support.md`.
Read all of it first.

**Prerequisites (all must have landed):** t2074_1 (classifiers), t2074_3
(setup recovery), and t2074_4 through t2074_8 (fixtures converted, retired
cases quarantined).

**Shared-file gate (first step):** `task_utils.sh` may carry uncommitted t2064
hunks.
- Run `git diff --quiet -- .aitask-scripts/lib/task_utils.sh` and confirm
  t2064's commit appears in `git log`.
- Re-run the check immediately before the first edit.
- Do all non-overlapping files first.
- If the gate still fails, stop and ask.

Also read any notes in this task's `## Inbox`, for example the `git-health`
item that t2074_1 may have handed over.

## Implementation

1. **Enforcers (C2), in `lib/task_utils.sh`.**
   - `ait_require_data_repo` dies unless C1a = `branch`.
     - It replaces rung 4's `_AIT_DATA_WORKTREE="."` inside
       `_ait_detect_data_worktree` (:145).
     - It also runs **first** in `assert_data_worktree_clean` (:434), which
       guards every `task_git`.
   - `ait_require_data_paths` dies unless C1a = `branch` and C1b = `ready`.
     - It runs **first** in `assert_task_data_writable` (:487), before the
       `AIT_GIT_SKIP_STATE_CHECK` bypass. From then on the bypass skips only
       the wedge check.
     - It runs at every reader entry point listed in C0.
     - It is **not** called from `assert_data_worktree_clean`. An unlinked
       crew worktree must still be able to route git.
   - Each enforcer prints a state-specific message naming the recovery from
     the C4 matrix.
2. **Delete every `"."` branch.**
   - `task_utils.sh`: `_ait_data_gitdir` :185, `ait_data_mode` :210 (remove it
     or make it constant), `_data_wedge_gitdir` :274, `_data_wedge_state` :282
     (merge it into `ait_data_inprogress_state`), `_ait_data_git` :298,
     `task_git_health` :513, `task_git` :552. Rewrite the comments at :40-76,
     :253-259, :432, :479 and :1570.
   - `aitask_sync.sh`: :279, :568-584, :696, and the comments at :4-6, :108,
     :1688 and :2000.
   - `lib/txn_snapshot.sh` :75; `lib/task_automerge.sh` :83.
   - Comments in `aitask_artifact.sh` :205, `lib/artifact_manifest.sh`,
     `lib/attachment_meta.sh`, `lib/artifact_backends/local.sh`,
     `lib/attachment_lock.sh` and `aitask_board_column.sh:113`.
3. **C3 errexit audit.** Enumerate every call site of the detection accessors
   written as `local x="$(…)"`, or guarded by `if` or `||`. `local` masks a
   `die` inside `$( )`. Fix each one by priming detection with a direct
   statement first, or by switching it to the classifier. Write one test per
   site. Move `aitask_gate.sh::_persist_task_file`'s non-git seam (:1049) onto
   the classifier.
4. **Writers reach the guard before their first write.** Audit update, create,
   archive, fold, note, gate, plan_externalize, board column and every
   atomic-write caller. Cover runs both with and without `--commit`. The
   relevant `aitask_update.sh` lines are :677, :1602, :1874 and :2291.
5. **Front door (C5).** The `ait` dispatcher maps every subcommand to its C0
   class.
   - Git routing needs C1a.
   - Readers and writers need C1a and C1b.
   - Exempt commands are setup, upgrade, install, help, version, engine,
     `git-health`, lock_diag, init_data and data_layout. Record a rationale
     for each.
   - An unmapped command fails closed to the reader class.
   - Commit the mapping table next to the dispatcher. Add a drift test that
     fails on any unmapped subcommand.
6. **Tokens (C6) and their consumers, in the same change.**
   - `aitask_remote_drift_check.sh`: remove `LEGACY_MODE_SKIP` (:144-154)
     **and** `--unsynced`, together with every call site.
   - `aitask_init_data.sh`: `LEGACY_MODE` becomes `NEEDS_CONVERSION` (exit 3)
     on both the plain path and `--link-worktree`. `NO_DATA_BRANCH` exits 3,
     still distinct from `NOT_INITIALIZED`. Update the help text.
   - `aitask_metadata_commit.sh:143-145`: `MODE:` is always `branch`. The line
     stays because `lib/metadata_commit.py:174` uses it for skew detection.
   - `aitask_lock_diag.sh:181`: `check_fail`, reporting the state and reason.
   - Skills, edited in the canonical `.claude/skills/` sources:
     - `task-workflow/remote-drift-check.md` :43-57 and :115;
       `task-workflow/merge-target-sync.md` :43-49.
     - `task-workflow/SKILL.md` Step 7: the `--link-worktree` token list
       (:561), and the wording at :551 ("silently degrades to legacy mode"
       becomes "broken layout").
     - `aitask-pickrem/SKILL.md.j2` and `aitask-pickweb/SKILL.md.j2` Step 0a:
       `NEEDS_CONVERSION` and `NO_DATA_BRANCH` now stop with the Stopped
       banner. Remove the "no-op for legacy repos" text.
   - Regenerate the goldens and the committed remote prerenders with repo
     tooling:
     - `./.aitask-scripts/aitask_skill_render.sh <skill> --profile <p> --agent <a> --force`
     - `aitask_skill_rerender.sh remote`
     - then `./.aitask-scripts/aitask_skill_verify.sh`

     The goldens live under `tests/golden/procs/task-workflow/` and
     `tests/golden/skills/aitask-{pickrem,pickweb}/`. Follow "Regenerate
     goldens after any `.md.j2` or closure edit" in
     `aidocs/framework/skill_authoring_conventions.md`.
7. **Retire the quarantine.** Delete every `tests/test_legacy_retired_*` file
   and add the refusal-test replacements. `test_task_git.sh` T15 (nested repo
   and submodule) becomes a refusal test. Update `test_init_data.sh` T9 (help)
   and T23. Re-run the T13c and T13d equivalents:
   - git ops work from both shapes;
   - a writer works inside `.aitask-data`;
   - a writer refuses in an unlinked worktree and creates no real `aitasks/`.
8. **Negative tests** in a new `tests/test_data_layout_refusal.sh`. The
   expectations come from C0:
   - **Unsupported C1a states** (every C1a state and reason, plus a nested
     repo): every non-exempt class refuses.
   - **Non-`ready` C1b with C1a = `branch`:** readers and writers refuse
     (`ait ls`, `aitask_query_files.sh`, a board-startup probe). Git routing
     **succeeds** (`./ait git status`, `task_git log`, `task_sync` against a
     remote fixture).
   - **Exempt commands** run in every state and report it.
   - **Fixtures carry dirty data:** a modified tracked task, an untracked new
     task, and ignored or untracked data (`aitasks/new/` drafts, a gitignored
     file under `aiplans/`).
   - **Commands under test:** `task_git add/commit`, `task_sync`, `task_push`,
     `./ait git pull/push`, `aitask_task_commit.sh`, `aitask_archive.sh`, and
     `aitask_update.sh --batch` both without `--commit` and with/without
     `AIT_GIT_SKIP_STATE_CHECK=1`.
   - **No-mutation proof:**
     - a before/after manifest (type, symlink target, mode, sha256) of every
       path under `aitasks/`, `aiplans/` and `.aitask-data/`, including
       ignored and untracked files;
     - snapshots of both repos: HEAD, every ref, `ls-files -s`,
       `status --porcelain --ignored`;
     - the bare remote's refs.
   - **Controls:** a positive control on a real branch-mode fixture for each
     case, and a planted write-before-refusal mutant that must make the
     manifest comparison fail.
9. **Post-phase `remote_skill_init_smoke`.** Freshly clone a branch-mode repo
   without running `ait setup`.
   - `aitask_init_data.sh` must print `INITIALIZED`, and the classifiers must
     then report `branch` / `ready`.
   - A legacy clone must give `NEEDS_CONVERSION` (exit 3).
   - A clone without the data branch must give `NO_DATA_BRANCH` (exit 3).
   - The pickrem/pickweb Step 0a table must map both of those to the Stopped
     banner.
10. **Notes.** Send notes to t1625 (its `LEGACY_MODE` link-token criterion),
    t1678 ("both modes"), t1984 (the legacy concurrency cell) and t1796
    (detection reasoning), each quoting the committed SHA. Use
    `./ait note <id> --from 2074_9`.

## Verification

- Run every `tests/test_*.sh` individually. All pass, with no probe.
- `bash tests/run_all_python_tests.sh`: the last line is
  `PYTHON SUITE: PASSED` (use `set -o pipefail`).
- `./.aitask-scripts/aitask_skill_verify.sh`, plus the
  `tests/test_skill_render_*.sh` golden checks.
- `shellcheck .aitask-scripts/aitask_*.sh`.
- By hand, in a temp legacy repo: `./ait ls`, `./ait git status` and a direct
  `aitask_update.sh --batch` are refused, and the manifest is unchanged.
  `ait setup` then converts the repo, and `diff -r` against a pre-conversion
  copy shows the data is identical.
