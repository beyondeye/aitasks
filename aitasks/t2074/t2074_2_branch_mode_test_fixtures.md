---
priority: high
effort: high
depends: [t2074_1]
issue_type: test
status: Ready
labels: [test_infrastructure, tests, git]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:31
updated_at: 2026-10-20 16:58
---

## Context

This is part of t2074 (rescoped: branch-mode layout hardening). **Legacy mode
stays supported.** t2074_9 makes the classification stricter (t2074_1's C1a
validation: live worktree, same repository, right branch). Some **branch-mode**
test fixtures build `.aitask-data` as a standalone repo, a clone, or a bare
`mkdir` stub instead of a registered worktree. The strict validation rejects
those fixtures as `broken:*`.

This work prepares those fixtures **before** enforcement lands. It is merged
into t2074_9 as that child's **Step A**. The binding contract is in
`aiplans/p2074_branch_mode_layout_hardening.md`.

## Scope (Step A)

Convert only the branch-mode fixtures that strict validation rejects. Keep each
fixture's signature, and read every builder before reusing it:
- `tests/lib/board_fixture.py` (`_layout`/`build_tree`/`build_fixture_tree`,
  `branch_mode=True`)
- `tests/lib/metadata_update_fixture.sh:188`
- `tests/test_task_push.sh:158 setup_branch_mode` (it moves a clone into
  `.aitask-data`). This is behind the t2064 shared-file gate in t2074_9
  Step 0.
- `tests/test_remote_drift_check.sh:111 mark_branch_mode` (a `mkdir
  .aitask-data` stub)
- `tests/test_plan_approved_marker_drift.sh:86` (a `mkdir -p
  .aitask-data/.git` stub)

Add a shared helper, `tests/lib/data_branch_fixture.sh`:
- `ait_fixture_to_branch_mode <repo> [--remote <bare>]`: a registered orphan
  `aitask-data` worktree at `.aitask-data`, built with production
  `ait_ensure_data_symlinks`, the `.gitignore` entries and the main-index
  removal. It pushes the data branch when a remote is given.
- `fixture_data_git`

Self-test: the helper's layout must classify `branch`/`ready`, the same as a
real `setup_data_branch` layout.

**Legacy fixtures stay unchanged.** Do not convert them.

**Measurement.** Run the whole suite once with the Step B validation applied
as a throwaway patch in an isolated `git worktree`. Never commit the patch.
This finds any other stubbed or clone-style branch layout; convert those too,
and record the list.

## Verification

- The self-test passes.
- Every test that uses a converted fixture passes: the board Python tests,
  `test_task_push.sh`, `test_remote_drift_check.sh`,
  `test_plan_approved_marker_drift.sh`, `test_usage_update.sh` and
  `test_verified_update.sh`.
