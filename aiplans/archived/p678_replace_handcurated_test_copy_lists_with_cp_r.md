---
Task: t678_replace_handcurated_test_copy_lists_with_cp_r.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Replace hand-curated test copy lists with `cp -R` (t678)

## Context

The macOS audit (t658) baseline run revealed three tests failing because their `setup_test_repo` functions hand-curate the list of `.aitask-scripts/*` files to copy into a scratch dir, and that list has gone stale as transitive deps were added:

- `tests/test_crew_groups.sh`, `tests/test_crew_report.sh` fail because `aitask_crew_init.sh` now sources `lib/launch_modes_sh.sh`, which is not in the hand-picked list.
- `tests/test_data_branch_migration.sh` fails Test 5 because `aitask_claim_id.sh` now sources `lib/archive_scan.sh`, which (although already present in the hand-picked list per current source — see note below) is illustrative of the broader drift problem.

`tests/test_crew_status.sh:98-102` already solved this with `cp -R`. The fix is to apply the same pattern to the three failing tests, eliminating the drift class entirely for these tests.

> Note: line 116 of `test_data_branch_migration.sh` actually does already copy `archive_scan.sh`. The task description's example may reflect a transient state, but the underlying drift risk is real for *future* additions; the `cp -R` switch removes the entire class of failure regardless of which specific file is missing today.

## Approach

For each of the three failing tests, replace the hand-curated `mkdir -p .aitask-scripts/...` + `cp ... .aitask-scripts/...` block in `setup_test_repo()` with the canonical pattern from `tests/test_crew_status.sh`:

```bash
cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts
find .aitask-scripts -type d -name __pycache__ -prune -exec rm -rf {} +
```

Keep the existing `chmod +x` lines for the scripts each test invokes (defensive — `cp -R` preserves perms, but the tests already rely on these being explicit).

Keep `mkdir -p` for non-`.aitask-scripts` paths (e.g. `aitasks/metadata`, `aitasks/archived`, `aiplans/archived`).

For `test_data_branch_migration.sh`, also keep `cp "$PROJECT_DIR/ait" ait` and the `echo "0.0.0-test" > .aitask-scripts/VERSION` line — they are independent of the scripts copy.

## Files to Modify

### 1. `tests/test_crew_groups.sh` (lines ~91-104)

Replace:
```bash
mkdir -p .aitask-scripts/lib .aitask-scripts/agentcrew aitasks/metadata

cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_init.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_addwork.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_command.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/__init__.py" .aitask-scripts/agentcrew/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_utils.py" .aitask-scripts/agentcrew/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_status.py" .aitask-scripts/agentcrew/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_runner.py" .aitask-scripts/agentcrew/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_report.py" .aitask-scripts/agentcrew/
chmod +x .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addwork.sh
chmod +x .aitask-scripts/aitask_crew_command.sh 2>/dev/null || true
```

With:
```bash
mkdir -p aitasks/metadata

# Mirror the full .aitask-scripts/ tree so transitive deps (e.g.
# lib/launch_modes_sh.sh) are present. Hand-curated copy lists drift
# silently as new sources/imports are added.
cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts
find .aitask-scripts -type d -name __pycache__ -prune -exec rm -rf {} +
chmod +x .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addwork.sh
chmod +x .aitask-scripts/aitask_crew_command.sh 2>/dev/null || true
```

### 2. `tests/test_crew_report.sh` (lines ~82-94)

Replace:
```bash
mkdir -p .aitask-scripts/lib .aitask-scripts/agentcrew aitasks/metadata

cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_init.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_addwork.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_cleanup.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/aitask_crew_report.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_utils.py" .aitask-scripts/agentcrew/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/agentcrew_report.py" .aitask-scripts/agentcrew/
cp "$PROJECT_DIR/.aitask-scripts/agentcrew/__init__.py" .aitask-scripts/agentcrew/
chmod +x .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addwork.sh
chmod +x .aitask-scripts/aitask_crew_cleanup.sh .aitask-scripts/aitask_crew_report.sh
```

With:
```bash
mkdir -p aitasks/metadata

# Mirror the full .aitask-scripts/ tree so transitive deps (e.g.
# lib/launch_modes_sh.sh) are present. Hand-curated copy lists drift
# silently as new sources/imports are added.
cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts
find .aitask-scripts -type d -name __pycache__ -prune -exec rm -rf {} +
chmod +x .aitask-scripts/aitask_crew_init.sh .aitask-scripts/aitask_crew_addwork.sh
chmod +x .aitask-scripts/aitask_crew_cleanup.sh .aitask-scripts/aitask_crew_report.sh
```

### 3. `tests/test_data_branch_migration.sh` (lines ~101-118)

Replace:
```bash
mkdir -p aitasks/metadata aitasks/archived aitasks/new
mkdir -p aiplans/archived
mkdir -p .aitask-scripts/lib

# Copy scripts from project
cp "$PROJECT_DIR/ait" ait
chmod +x ait
cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/aitask_ls.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" .aitask-scripts/
cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/
chmod +x .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_update.sh
chmod +x .aitask-scripts/aitask_claim_id.sh .aitask-scripts/aitask_setup.sh
```

With:
```bash
mkdir -p aitasks/metadata aitasks/archived aitasks/new
mkdir -p aiplans/archived

# Copy ait dispatcher
cp "$PROJECT_DIR/ait" ait
chmod +x ait

# Mirror the full .aitask-scripts/ tree so transitive deps are present.
# Hand-curated copy lists drift silently as new sources/imports are added.
cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts
find .aitask-scripts -type d -name __pycache__ -prune -exec rm -rf {} +
chmod +x .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_update.sh
chmod +x .aitask-scripts/aitask_claim_id.sh .aitask-scripts/aitask_setup.sh
```

The subsequent line `echo "0.0.0-test" > .aitask-scripts/VERSION` (currently line 121) is left untouched — it overwrites the source repo's VERSION file with a test-stable value, and must run after `cp -R`.

## Reference

`tests/test_crew_status.sh:84-104` — canonical implementation of the pattern.

## Verification

Run all three tests on Linux (current platform). Linux runs are sufficient per the task description; the failure mode is platform-agnostic.

```bash
bash tests/test_crew_groups.sh
bash tests/test_crew_report.sh
bash tests/test_data_branch_migration.sh
```

Each must report a final PASS / 0 failures. Also run `tests/test_crew_status.sh` as a smoke test that the canonical pattern still works:

```bash
bash tests/test_crew_status.sh
```

Step 9 (Post-Implementation) of the task workflow handles archival.

## Final Implementation Notes

- **Actual work done:** Replaced the hand-curated copy blocks in `setup_test_repo()` of `tests/test_crew_groups.sh`, `tests/test_crew_report.sh`, and `tests/test_data_branch_migration.sh` with the canonical `cp -R "$PROJECT_DIR/.aitask-scripts" .aitask-scripts` + `find ... __pycache__ ... rm -rf` pattern from `tests/test_crew_status.sh:98-102`. Trimmed `mkdir -p .aitask-scripts/...` lines that became unnecessary (the recursive copy creates the tree). Preserved the existing `chmod +x` lines defensively, the unrelated mkdirs (`aitasks/metadata`, `aitasks/archived`, `aiplans/archived`), and — in `test_data_branch_migration.sh` — the `cp "$PROJECT_DIR/ait" ait` step and the post-copy `echo "0.0.0-test" > .aitask-scripts/VERSION` override.
- **Deviations from plan:** None. The plan was applied verbatim.
- **Issues encountered:** None. All four verification commands passed first try (24/24, 28/28, 21/21, 57/57 — last is the smoke run of `test_crew_status.sh`).
- **Key decisions:** Excluded unrelated pre-existing working-tree changes (`.aitask-scripts/aitask_setup.sh` modification, untracked `tests/test_setup_find_modern_python.sh` and `tests/test_setup_python_install.sh`) from the t678 commit — they belong to a separate effort.
- **Upstream defects identified:** None.
