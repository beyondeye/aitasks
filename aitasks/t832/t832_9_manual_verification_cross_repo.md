---
priority: medium
effort: medium
depends: [t832_8]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [t832_1, t832_2, t832_3, t832_4, t832_5, t832_6, t832_7, t832_8]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-26 18:39
updated_at: 2026-05-31 17:48
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [x] [t832_1] `bash tests/test_query_files_cross_repo.sh` passes. — PASS 2026-05-31 16:47 auto: test_query_files_cross_repo.sh 34/34
- [x] [t832_1] `shellcheck .aitask-scripts/aitask_query_files.sh .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_find_by_file.sh` clean. — PASS 2026-05-31 16:47 auto: shellcheck query_files/ls/find_by_file: SC1091 + pre-existing baseline only, none from t832
- [skip] [t832_1] Manual: from `aitasks_mobile`, `./.aitask-scripts/aitask_query_files.sh task-file --project aitasks 832` returns the t832 path in aitasks. — SKIP 2026-05-31 17:13 re-exec capability proven by item 5; sibling aitasks_mobile script predates --project (needs upgrade). Not blocking.
- [x] [t832_1] `./.aitask-scripts/aitask_skill_verify.sh` passes (helpers remain skill-invokable). — PASS 2026-05-31 16:47 auto: aitask_skill_verify.sh OK (10 templates/3 agents)
- [x] [t832_1] `--project <registered>` re-execs into the correct project root. — PASS 2026-05-31 16:47 auto: --project aitasks_mobile re-exec returns mobile t10 path
- [x] [t832_1] `--project <unregistered>` dies with the `cd && ait projects add` hint. — PASS 2026-05-31 16:47 auto: --project unregistered dies rc=1 with 'cd && ait projects add' hint
- [x] [t832_1] `--project <stale>` dies with the stale-path message. — PASS 2026-05-31 16:47 auto: --project stale dies rc=1 with stale-path refresh message
- [x] [t832_1] `task-status` returns the correct status for each lifecycle state. — PASS 2026-05-31 16:47 auto: task-status Implementing/Done/Ready all correct
- [x] [t832_1] `task-status NOT_FOUND` is silent (no crash). — PASS 2026-05-31 16:47 auto: task-status 9999999 -> STATUS:NOT_FOUND rc=0, no crash
- [x] [t832_1] `aitask_skill_verify.sh` passes. — PASS 2026-05-31 16:47 auto: aitask_skill_verify.sh OK (same run as item 4)
- [x] [t832_2] `bash tests/test_explain_context_cross_repo.sh` passes. — PASS 2026-05-31 16:47 auto: test_explain_context_cross_repo.sh 22/22
- [x] [t832_2] `shellcheck .aitask-scripts/aitask_explain_context.sh` clean. — PASS 2026-05-31 16:47 auto: shellcheck explain_context.sh: SC1091 only
- [skip] [t832_2] Manual: from `aitasks`, — SKIP 2026-05-31 17:15 manual step truncated; functional coverage via item 11 (explain_context test 22/22)
- [x] [t832_3] `bash tests/test_xdeps_parser.sh` / `test_xdeps_validation.sh` / — PASS 2026-05-31 16:47 auto: xdeps_parser 5/5, xdeps_validation 14/14, xdeps_fold_warn 9/9
- [x] [t832_3] `shellcheck` clean on touched scripts. — PASS 2026-05-31 16:47 auto: shellcheck create/fold_validate/ls/update: baseline warnings (blame=initial import), none from t832
- [x] [t832_3] TUI round-trip: create a task with `xdeps` / `xdeprepo`, open in `ait — PASS 2026-05-31 17:48 auto(tmux+serialize): board save path preserves xdeps:[1]/xdeprepo on priority change medium->high
- [x] [t832_4] `bash tests/test_xdeps_blocking.sh` passes. — PASS 2026-05-31 16:47 auto: test_xdeps_blocking.sh 18/18
- [x] [t832_4] `shellcheck .aitask-scripts/aitask_ls.sh` clean. — PASS 2026-05-31 16:47 auto: shellcheck aitask_ls.sh: baseline-only warnings, none from t832
- [skip] [t832_4] Manual: `./.aitask-scripts/aitask_ls.sh -v 5` against a real cross-repo — SKIP 2026-05-31 17:15 blocking logic covered by item 17 (test_xdeps_blocking 18/18); live-board flag not separately verified
- [x] TODO: define verification for t832_5 — PASS 2026-05-31 16:47 auto: TODO placeholder; t832_5 verified via test_parallel_cross_repo_planning_procedure.sh 36/36
- [defer] [t832_6] `aidocs/cross_repo_retrospective_t832.md` exists with all sections — DEFER 2026-05-31 16:57 auto: blocked: aidocs/cross_repo_retrospective_t832.md missing - t832_6 still pending
- [defer] [t832_6] Each filed follow-up task body references this retrospective and the — DEFER 2026-05-31 16:57 auto: blocked: depends on t832_6 retrospective + filed follow-ups, not yet implemented
- [defer] [t832_6] If zero friction: the audit document explicitly states "no follow-ups — DEFER 2026-05-31 16:57 auto: blocked: depends on t832_6 audit doc, not yet implemented
- [x] [t832_7] `bash tests/test_update_cross_repo.sh` passes. — PASS 2026-05-31 16:47 auto: test_update_cross_repo.sh 41/41 + test_aitask_update_xdeps.sh 20/20
- [x] [t832_7] `shellcheck .aitask-scripts/aitask_update.sh` clean. — PASS 2026-05-31 16:47 auto: shellcheck aitask_update.sh: baseline-only warnings, none from t832
- [skip] [t832_7] Manual: from `aitasks`, — SKIP 2026-05-31 17:15 would mutate sibling repo task data (--add-label); avoided per no-mutation policy; update logic covered by item 24
- [x] [t832_8] `bash tests/test_cross_repo_notation.sh` passes (or equivalent — PASS 2026-05-31 16:47 auto: test_cross_repo_notation.py 9/9 (equivalent to .sh)
- [x] [t832_8] `./.aitask-scripts/aitask_skill_verify.sh` passes (no skill changes, — PASS 2026-05-31 16:47 auto: aitask_skill_verify.sh OK (same run as item 4)
- [x] [t832_8] `shellcheck` clean if any new bash wrappers are introduced. — PASS 2026-05-31 16:47 auto: no new bash wrappers in t832_8; edited bash scripts baseline-only
- [x] [t832_8] Launch `ait board` in project A. A task with `xdeps: [1]` — PASS 2026-05-31 17:48 auto(tmux board): card shows distinct '↗ av_projB#1' cross-repo dep line
- [x] [t832_8] That same task shows "blocked by cross-repo" indicator (assuming — PASS 2026-05-31 17:48 auto(tmux board): card shows distinct '🌐 blocked (cross-repo)' indicator when dep unmet
- [x] [t832_8] When B/t1's status changes to Done (out-of-band) and the board — PASS 2026-05-31 17:48 auto(tmux board): projB#1->Done out-of-band + refresh cleared blocked chip, card shows Ready
- [skip] [t832_8] Stale-registry case: edit `~/.config/aitasks/projects.yaml` to point — SKIP 2026-05-31 17:15 would mutate real ~/.config/aitasks/projects.yaml; resolver-level stale handling already verified in item 7
- [skip] [t832_8] Restore registry. — SKIP 2026-05-31 17:15 paired with item 33 (registry restore); not run since 33 not mutated
- [x] [t832_8] Open a task whose body contains `aitasks#42`. Activate the link. — PASS 2026-05-31 17:48 auto(tmux board): '#' opens read-only popup with cross-repo task content (no lock); ESC closes, board unchanged
- [x] [t832_8] Activate a link to a non-registered project. The popup shows the — PASS 2026-05-31 17:48 auto(tmux board): '#' on single non-registered ref opens error popup 'Project ghost_proj is not registered...'; no crash
