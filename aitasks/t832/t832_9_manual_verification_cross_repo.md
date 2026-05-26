---
priority: medium
effort: medium
depends: [t832_8]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [832_1, 832_2, 832_3, 832_4, 832_5, 832_6, 832_7, 832_8]
created_at: 2026-05-26 18:39
updated_at: 2026-05-26 18:39
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t832_1] `bash tests/test_query_files_cross_repo.sh` passes.
- [ ] [t832_1] `shellcheck .aitask-scripts/aitask_query_files.sh .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_find_by_file.sh` clean.
- [ ] [t832_1] Manual: from `aitasks_mobile`, `./.aitask-scripts/aitask_query_files.sh task-file --project aitasks 832` returns the t832 path in aitasks.
- [ ] [t832_1] `./.aitask-scripts/aitask_skill_verify.sh` passes (helpers remain skill-invokable).
- [ ] [t832_1] `--project <registered>` re-execs into the correct project root.
- [ ] [t832_1] `--project <unregistered>` dies with the `cd && ait projects add` hint.
- [ ] [t832_1] `--project <stale>` dies with the stale-path message.
- [ ] [t832_1] `task-status` returns the correct status for each lifecycle state.
- [ ] [t832_1] `task-status NOT_FOUND` is silent (no crash).
- [ ] [t832_1] `aitask_skill_verify.sh` passes.
- [ ] [t832_2] `bash tests/test_explain_context_cross_repo.sh` passes.
- [ ] [t832_2] `shellcheck .aitask-scripts/aitask_explain_context.sh` clean.
- [ ] [t832_2] Manual: from `aitasks`,
- [ ] [t832_3] `bash tests/test_xdeps_parser.sh` / `test_xdeps_validation.sh` /
- [ ] [t832_3] `shellcheck` clean on touched scripts.
- [ ] [t832_3] TUI round-trip: create a task with `xdeps` / `xdeprepo`, open in `ait
- [ ] [t832_4] `bash tests/test_xdeps_blocking.sh` passes.
- [ ] [t832_4] `shellcheck .aitask-scripts/aitask_ls.sh` clean.
- [ ] [t832_4] Manual: `./.aitask-scripts/aitask_ls.sh -v 5` against a real cross-repo
- [ ] TODO: define verification for t832_5
- [ ] [t832_6] `aidocs/cross_repo_retrospective_t832.md` exists with all sections
- [ ] [t832_6] Each filed follow-up task body references this retrospective and the
- [ ] [t832_6] If zero friction: the audit document explicitly states "no follow-ups
- [ ] [t832_7] `bash tests/test_update_cross_repo.sh` passes.
- [ ] [t832_7] `shellcheck .aitask-scripts/aitask_update.sh` clean.
- [ ] [t832_7] Manual: from `aitasks`,
- [ ] [t832_8] `bash tests/test_cross_repo_notation.sh` passes (or equivalent
- [ ] [t832_8] `./.aitask-scripts/aitask_skill_verify.sh` passes (no skill changes,
- [ ] [t832_8] `shellcheck` clean if any new bash wrappers are introduced.
- [ ] [t832_8] Launch `ait board` in project A. A task with `xdeps: [1]`
- [ ] [t832_8] That same task shows "blocked by cross-repo" indicator (assuming
- [ ] [t832_8] When B/t1's status changes to Done (out-of-band) and the board
- [ ] [t832_8] Stale-registry case: edit `~/.config/aitasks/projects.yaml` to point
- [ ] [t832_8] Restore registry.
- [ ] [t832_8] Open a task whose body contains `aitasks#42`. Activate the link.
- [ ] [t832_8] Activate a link to a non-registered project. The popup shows the
