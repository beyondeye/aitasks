---
Task: t83_commit_after_import.md
Branch: main (no worktree)
Base branch: main
---

## Context

The `aitask_import.sh` interactive mode creates tasks from GitHub issues but doesn't offer to commit the new task to git afterward. The `aitask_create.sh` interactive mode already has this feature (lines 1102-1124). Additionally, `aitask_update.sh` lacks a `--commit` option entirely. The goal is consistent git commit support across all three scripts.

## Current State

| Script | Interactive commit | Batch `--commit` |
|--------|-------------------|-------------------|
| `aitask_create.sh` | Yes (line 1102) | Yes (line 916) |
| `aitask_import.sh` | **No** | Yes (line 322, passes to aitask_create) |
| `aitask_update.sh` | **No** | **No** |

## Changes

### 1. `aitask_import.sh` - Add interactive mode commit (line ~567)

After `success "Created: $result"` in `interactive_import_issue()`, add a git commit prompt.

**Note:** The batch import path already passes `--commit` through to `aitask_create.sh` (line 322), so batch mode is already handled.

### 2. `aitask_update.sh` - Add `--commit` flag

- Add `BATCH_COMMIT=false` variable
- Add `--commit` to `parse_args()`
- Add batch commit logic at end of `run_batch_mode()`
- Add interactive commit prompt at end of `run_interactive_mode()`
- Update help text with `--commit` option

### 3. Help text consistency

- `aitask_create.sh`: already documented
- `aitask_import.sh`: already documented
- `aitask_update.sh`: add `--commit` to help

## Files to Modify

1. `aitask_import.sh` - Add commit prompt in `interactive_import_issue()`
2. `aitask_update.sh` - Add BATCH_COMMIT variable, parse --commit, commit logic, help text

## Final Implementation Notes
- **Actual work done:** Exactly as planned. Added interactive commit prompt to `aitask_import.sh` and full `--commit` support (batch + interactive) to `aitask_update.sh`.
- **Deviations from plan:** None.
- **Issues encountered:** None. Both scripts passed syntax validation cleanly.
- **Key decisions:** Used `sed 's/^t[0-9]*_\([0-9]*_\)\?//'` pattern in aitask_update.sh to handle both parent (t83_name) and child (t83_1_name) task filename formats when generating humanized names for commit messages.
