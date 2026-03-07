---
Task: t328_fix_preexisting_test_data_branch_setup_failures.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Fix pre-existing test_data_branch_setup failures (t328)

## Context

`update_claudemd_git_section()` now uses `assemble_aitasks_instructions()` which reads from `aitasks/metadata/aitasks_agent_instructions.seed.md`. Tests 1, 6, 7, 8 in `test_data_branch_setup.sh` fail because their temp directories lack this seed file, causing `assemble_aitasks_instructions` to return 1 silently and skip CLAUDE.md creation/update.

There's also a production bug: `setup_data_branch()` copies various seed files (task_types.txt, project_config.yaml, etc.) but omits `*_instructions.seed.md` files.

## Changes

### 1. Production fix: `setup_data_branch()` in `.aitask-scripts/aitask_setup.sh`

Added `*_instructions.seed.md` to the seed copy block (after models_*.json copy). This ensures `ait setup` on real projects copies the instruction seed files to the data branch.

### 2. Test fixture fixes: `tests/test_data_branch_setup.sh`

- Added `setup_seed_file()` helper that copies the real seed file to `aitasks/metadata/` in a temp dir
- Test 1: Added `seed/` directory with seed file to test repo so `setup_data_branch`'s copy block can find it
- Tests 6, 7, 8: Added `setup_seed_file` call to create the seed file (simulating post-setup state)

## Verification

All 44 tests pass (0 failures).

## Final Implementation Notes
- **Actual work done:** Fixed production bug in `setup_data_branch()` (missing seed file copy) and updated 4 test fixtures (tests 1, 6, 7, 8) to include the seed file
- **Deviations from plan:** None — implemented exactly as planned
- **Issues encountered:** None
- **Key decisions:** Used `cp` of the real seed file from `seed/` rather than inlining content, so tests stay in sync with the source of truth
