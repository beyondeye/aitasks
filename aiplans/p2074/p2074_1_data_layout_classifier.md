---
Task: t2074_1_data_layout_classifier.md
Parent Task: aitasks/t2074_branch_mode_layout_hardening.md
Sibling Tasks: aitasks/t2074/t2074_3_setup_layout_repair.md, aitasks/t2074/t2074_9_branch_layout_enforcement.md, aitasks/t2074/t2074_12_broken_layout_docs.md, aitasks/t2074/t2074_14_manual_verification_branch_mode_layout_hardening.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_1: Data layout classifiers (C1a / C1b)

This child is additive only, and legacy mode keeps its current behaviour. The
binding contract is C1a, C1b and the no-marker table in
`aiplans/p2074_branch_mode_layout_hardening.md`. The full detail is in the task
description.

## Steps
1. Read `lib/data_symlinks.sh`: `ait_main_worktree_root`,
   `ait_linked_worktree_roots`, `ait_canon_path`, `ait_data_link_target` and
   `AIT_DATA_LINKS`. Also read `_ait_detect_data_worktree` and
   `_ait_inprogress_state_at` in `task_utils.sh`.
2. Implement `ait_data_repo_state`:
   - Resolution order: data worktree, then local marker, then main-root
     fallback. If none applies, apply the no-marker precedence rows 1-4.
   - Validation order: `stale_marker`, then `foreign_repo`, then
     `wrong_branch`. A detached HEAD whose rebase `head-name` or
     `BISECT_START` names `aitask-data` is treated as wedged, not broken.
   - Return `indeterminate:topology` as a state; never die on it.
3. Implement `ait_data_paths_state`: `ready`, `unlinked`, `misdirected`,
   `dangling`, `mixed`, plus `legacy`.
4. Make it errexit-safe throughout: every internal `$( )` gets `|| var=""`
   with an explicit failure branch. Check the filesystem first and fall back
   to git. Cache the result per process and comment why that is valid.
5. Add the `aitask_data_layout.sh` CLI and its whitelist touchpoints, then
   `lib/data_layout.py` (`snapshot()` cached; the `require_*()` functions
   fresh).
6. `git-health` reporting: apply the t2064 shared-file gate on
   `task_utils.sh`. If the gate blocks, send a note handing the work to
   t2074_9.
7. Tests: one fixture per state and reason, every `missing_storage` row, the
   positive cases (T13c, T13d, linked, separate-git-dir, mid-rebase,
   mid-bisect, nested), the legacy controls, never-dies under errexit, the
   filesystem-vs-git differential, Python/shell parity, and the fresh
   re-evaluation of `require_*()`.

## Verification
Run the new tests, plus `tests/test_task_git.sh`, `tests/test_init_data.sh`
and `shellcheck`.

## Step 9
Commit with `feature: … (t2074_1)`, then archive.
