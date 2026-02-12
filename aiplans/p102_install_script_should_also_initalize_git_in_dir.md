---
Task: t102_install_script_should_also_initalize_git_in_dir.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The aitask framework is designed to live inside a project's git repository, but the setup script (`ait setup`) currently assumes git is already initialized. This task adds git initialization and initial commit support to the setup script.

## Plan

### File modified
- `aiscripts/aitask_setup.sh` — Added `setup_git_repo()` function

### New file
- `tests/test_setup_git.sh` — Automated tests for the new function

### Changes

1. Added `setup_git_repo()` function that:
   - Checks if current directory is already a git repo (skips if so)
   - If not, warns and offers to `git init`
   - If user accepts init, offers to commit framework files (aiscripts/, aitasks/metadata/, ait, .claude/skills/, VERSION, install.sh)
   - If user refuses commit, re-emphasizes importance and asks "are you sure?" — respects final refusal
   - If user refuses init entirely, warns but continues setup

2. Called from `main()` right after `install_cli_tools` (so git binary is available)

### Verification
- [x] `bash -n aiscripts/aitask_setup.sh` — syntax check passes
- [x] 16 automated tests pass (`bash tests/test_setup_git.sh`)
- [x] Manual test: existing repo detected correctly

## Final Implementation Notes
- **Actual work done:** Added `setup_git_repo()` function to `aitask_setup.sh` and comprehensive automated tests in `tests/test_setup_git.sh`. Implemented exactly as planned.
- **Deviations from plan:** None — implementation matched the plan.
- **Issues encountered:** Test script initially failed because sourcing `aitask_setup.sh` imports `set -euo pipefail`, causing `git log` on empty repos (exit code 128) to kill the test. Fixed by disabling strict mode after sourcing and using `|| echo 0` for git log calls on potentially empty repos.
- **Key decisions:** Placed `setup_git_repo` call after `install_cli_tools` in `main()` to ensure `git` binary is available. The function uses `git -C "$project_dir"` throughout to work correctly regardless of the current working directory.
