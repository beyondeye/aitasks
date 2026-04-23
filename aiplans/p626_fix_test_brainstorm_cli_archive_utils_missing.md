---
Task: t626_fix_test_brainstorm_cli_archive_utils_missing.md
Base branch: main
plan_verified: []
---

## Context

`bash tests/test_brainstorm_cli.sh` fails on `main` with:
```
.aitask-scripts/lib/task_utils.sh: line 14:
  .aitask-scripts/lib/archive_utils.sh: No such file or directory
```

Root cause: `lib/task_utils.sh:13-14` unconditionally sources `lib/archive_utils.sh`. `tests/test_brainstorm_cli.sh::setup_test_repo()` copies `terminal_compat.sh`, `agentcrew_utils.sh`, and `task_utils.sh` into a scratch repo but not `archive_utils.sh`, so any scratch-repo script that sources `task_utils.sh` dies at source time.

## Scope

Fix the failing test **and** all sibling tests that copy `task_utils.sh` into a scratch `.aitask-scripts/lib/` without copying `archive_utils.sh`. Tests that merely `source` `task_utils.sh` directly from `$PROJECT_DIR` are unaffected (the real `lib/` already has `archive_utils.sh` alongside).

Affected tests (scratch-repo `cp`, needs paired copy of `archive_utils.sh`):

- `tests/test_brainstorm_cli.sh` — line 98 (the originally failing test)
- `tests/test_issue_import_contributor.sh` — line 91
- `tests/test_pr_contributor_metadata.sh` — line 73
- `tests/test_parallel_child_create.sh` — line 79
- `tests/test_verified_update.sh` — line 83
- `tests/test_contribute.sh` — lines 104, 619 (two scratch-repo setups)
- `tests/test_data_branch_migration.sh` — line 114
- `tests/test_lock_diag.sh` — line 73
- `tests/test_lock_force.sh` — line 97
- `tests/test_revert_analyze.sh` — line 88
- `tests/test_task_push.sh` — lines 289, 316 (two scratch `cp` sites; it also sources from PROJECT_DIR at line 111, which is unaffected)

Unaffected (do not touch):

- Tests sourcing from `$PROJECT_DIR` only: `test_task_git.sh`, `test_last_used_labels.sh`, `test_format_yaml_list.sh`, `test_merge_issues.sh`, `test_sed_compat.sh`, `test_resolve_tar_zst.sh`
- `test_explain_context.sh` — writes its own minimal stub `task_utils.sh` without the offending `source` line
- `test_extract_auto_naming.sh`, `test_find_files.sh`, `test_no_recurse.sh` — reference `task_utils.sh` only as a path input (not copied/sourced)

## Implementation

For each affected `cp` site, append a companion `cp` line for `archive_utils.sh` with the same destination style as the existing `task_utils.sh` line. Match indentation and quoting of the surrounding lines.

Example (pattern for every site):
```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
```

For `test_verified_update.sh`, `test_contribute.sh`, `test_task_push.sh`, and `test_revert_analyze.sh` the destination uses a variable (e.g. `"$repo_dir/.aitask-scripts/lib/"`, `"$local_dir/.aitask-scripts/lib/"`, `"$tmpdir/.aitask-scripts/lib/"`, `"$PROJECT_TEST_DIR/.aitask-scripts/lib/"`, or plain `.aitask-scripts/lib/`) — mirror the destination used by the paired `task_utils.sh` line in each file.

No changes to `lib/task_utils.sh` or `lib/archive_utils.sh` themselves — the framework side is correct; only the test scaffolding was incomplete.

## Verification

1. Reproduce failure cleared:
   ```bash
   bash tests/test_brainstorm_cli.sh
   ```
   Exits 0; no `archive_utils.sh: No such file or directory` in output.

2. Audit grep returns empty for the scratch-repo pattern:
   ```bash
   # Find tests that cp task_utils.sh into a scratch lib/ but don't cp archive_utils.sh
   for f in tests/*.sh; do
     if grep -q 'cp .*task_utils\.sh' "$f" && ! grep -q 'cp .*archive_utils\.sh' "$f"; then
       echo "MISSING: $f"
     fi
   done
   ```
   Should print nothing.

3. Shellcheck stays clean on every modified test:
   ```bash
   shellcheck tests/test_brainstorm_cli.sh tests/test_issue_import_contributor.sh \
     tests/test_pr_contributor_metadata.sh tests/test_parallel_child_create.sh \
     tests/test_verified_update.sh tests/test_contribute.sh \
     tests/test_data_branch_migration.sh tests/test_lock_diag.sh \
     tests/test_lock_force.sh tests/test_revert_analyze.sh \
     tests/test_task_push.sh
   ```

4. Spot-check a couple of previously-passing tests still pass (they were not failing, but the added `cp` line is a no-op-enabler and should not regress them):
   ```bash
   bash tests/test_lock_diag.sh
   bash tests/test_verified_update.sh
   ```

Post-implementation cleanup, archival, and merge follow the standard task-workflow **Step 9 (Post-Implementation)**.

## Final Implementation Notes

- **Actual work done:**
  - Added `cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" <dest>/.aitask-scripts/lib/` paired with the existing `task_utils.sh` copy in all 11 identified test scaffolds (12 `cp` sites — `test_contribute.sh` and `test_task_push.sh` have two each).
  - Additionally added `cp .../lib/archive_scan.sh` in `tests/test_brainstorm_cli.sh` after the first fix exposed a secondary missing-source failure from `aitask_query_files.sh` (which the test copies and which sources `lib/archive_scan.sh` at line 30). The `archive_scan.sh` addition is scoped to this one test file only — it is not part of the documented task scope and is not propagated to the other 10 tests.
  - No changes to framework code (`lib/*.sh`) — the framework side was correct; only test scaffolding was incomplete.

- **Deviations from plan:** None in scope. Added the archive_scan.sh line in `test_brainstorm_cli.sh` only (see above) — a narrow, local scope extension needed to progress past the original documented failure.

- **Issues encountered:**
  - After both sourcing fixes, `test_brainstorm_cli.sh` still fails with **different, unrelated** pre-existing issues:
    1. `codeagent_config.json` in the scratch repo is missing `brainstorm-explorer`, `brainstorm-comparator`, `brainstorm-synthesizer`, `brainstorm-detailer`, `brainstorm-patcher`, `brainstorm-initializer` entries — `aitask_brainstorm_init.sh` errors out building the crew.
    2. `aitask_crew_init.sh` sources `.aitask-scripts/lib/launch_modes_sh.sh` which the test does not copy.
  - These are separate bugs, predating this task and uncovered only because the archive_utils.sh fix let execution reach them. They should be handled as follow-up tasks — the task description explicitly said to fix the `archive_utils.sh` missing-copy pattern, not to wire up brainstorm crew config in the scratch repo.

- **Key decisions:**
  - Kept the fix additive and pattern-based: every site that copies `task_utils.sh` into a scratch `lib/` now also copies `archive_utils.sh`. This maps 1:1 onto the unconditional `source` at `lib/task_utils.sh:13-14`, so future test-authors cloning the existing pattern inherit a correct scaffold.
  - Excluded `test_explain_context.sh` (writes its own minimal stub `task_utils.sh` without the offending `source` line) and the six tests that `source` `task_utils.sh` directly from `$PROJECT_DIR` (the real project `lib/` already has `archive_utils.sh` alongside).
  - Did NOT commit an unrelated pre-existing modification to `.aitask-scripts/brainstorm/brainstorm_app.py` that was present in the working tree at task start.

- **Verification:**
  - Audit grep (`for f in tests/*.sh; do if grep -q 'cp .*lib/task_utils\.sh' "$f" && ! grep -q 'cp .*lib/archive_utils\.sh' "$f"; then echo MISSING; fi; done`) returns empty.
  - `shellcheck --severity=error` clean on all 11 modified tests.
  - Regression spot-checks: `test_verified_update.sh` (54/54 pass) and `test_lock_diag.sh` (9/9 pass).
  - `test_brainstorm_cli.sh` no longer dies at the documented `archive_utils.sh: No such file or directory` — it reaches the next (unrelated) failure layer.

- **Recommended follow-ups** (for `aitask-create`):
  1. `tests/test_brainstorm_cli.sh` — seed a valid `codeagent_config.json` (or mocked `codeagent_config_loader` path) with the `brainstorm-*` agent keys needed by `aitask_brainstorm_init.sh`.
  2. `tests/test_brainstorm_cli.sh` — copy `.aitask-scripts/lib/launch_modes_sh.sh` in `setup_test_repo()` so `aitask_crew_init.sh` can source it.
  3. Broader audit: check whether other tests that copy `aitask_query_files.sh` / `aitask_claim_id.sh` (both source `archive_scan.sh`) also need `archive_scan.sh` paired — candidates from `grep -l 'aitask_query_files.sh\\|aitask_claim_id.sh' tests/*.sh` include `test_claim_id.sh`, `test_create_silent_stdout.sh`, `test_file_references.sh`, `test_create_manual_verification.sh`, `test_draft_finalize.sh`, `test_parallel_child_create.sh`, `test_auto_merge_file_ref.sh`, `test_setup_git.sh`, `test_data_branch_migration.sh`, `test_issue_import_contributor.sh`, `test_pr_contributor_metadata.sh`, `test_query.sh`, `test_revert_analyze.sh`, `test_verification_followup.sh`.
