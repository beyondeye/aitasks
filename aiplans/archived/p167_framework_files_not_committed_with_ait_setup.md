---
Task: t167_framework_files_not_committed_with_ait_setup.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Fix: Framework Files Not Committed with `ait setup` (t167)

## Context

When running `ait setup` in a new project directory (with git already configured), framework files are installed but not committed to git. Evidence from test repo at `/home/ddt/Work/TESTS/test_repo_bitbucket` shows all framework files as untracked.

**Root causes:**
1. `install.sh` extracts files but never commits them — it only tells the user to run `ait setup`
2. In `aitask_setup.sh`, `setup_git_repo()` commits files EARLY in the flow, but later steps (`setup_review_modes`, `setup_draft_directory`) create additional files that are never committed
3. If `ait setup` fails early (e.g., during `install_cli_tools`), the commit step is never reached

## Implementation

### 1. Restructured `aitask_setup.sh`
- [x] Split `setup_git_repo()` into `ensure_git_repo()` (git init only) and `commit_framework_files()` (commits everything at the end)
- [x] `commit_framework_files()` runs after ALL setup steps, picking up review guides, .gitignore, etc.
- [x] Updated `main()` to use new function names and ordering

### 2. Added `commit_installed_files()` to `install.sh`
- [x] Safety net: commits framework files after extraction, before user runs `ait setup`
- [x] Silent (no prompt) since stdin may not be a terminal
- [x] Non-fatal on failure

### 3. Updated tests (`tests/test_setup_git.sh`)
- [x] Updated Tests 1-5 to use `ensure_git_repo` + `commit_framework_files`
- [x] Added Test 10: late-stage files (review guides, .gitignore)
- [x] Added Test 11: idempotency
- [x] Added Test 12: missing install.sh handling
- [x] Added Test 13: ensure_git_repo does NOT commit

### 4. Created integration test (`tests/test_t167_integration.sh`)
- [x] Scenario A: install.sh auto-commits
- [x] Scenario B: commit_framework_files catches late-stage files
- [x] Scenario C: idempotency
- [x] Scenario D: fresh install with install.sh then commit_framework_files
- [x] Scenario E: non-git directory

## Key Design Decisions

- `.claude/settings.local.json` is NOT committed (local per-developer)
- `setup_draft_directory`'s independent `.gitignore` commit is left as-is
- `install.sh` commits silently (no prompt) since stdin may not be a terminal

## Verification

- `bash tests/test_setup_git.sh` — 33/33 passed
- `bash tests/test_t167_integration.sh` — 11/11 passed
- `bash tests/test_global_shim.sh` — 15/15 passed (no regressions)

## Final Implementation Notes
- **Actual work done:** Split `setup_git_repo()` into `ensure_git_repo()` + `commit_framework_files()`, added `commit_installed_files()` to install.sh, comprehensive test coverage
- **Deviations from plan:** Test 14 (install.sh sourcing) was replaced by integration test scenarios which provide better end-to-end coverage
- **Issues encountered:** Integration test initially included `install.sh` in the tarball (unlike real releases), causing a false test failure — fixed by matching real tarball structure
- **Key decisions:** `.claude/settings.local.json` excluded from commit (per-developer local settings); `setup_draft_directory`'s separate .gitignore commit preserved for clean git history
