---
Task: t389_fix_check_imported_pipefail_crash.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

## Context

The `check-imported` subcommand in `aitask_contribution_review.sh` crashes with exit code 1 when no matching task is found. It should output `NOT_IMPORTED` but instead silently aborts due to `set -euo pipefail` interacting with `grep -rl` returning exit code 1 on no matches.

## Plan

### Step 1: Fix `cmd_check_imported()` in `.aitask-scripts/aitask_contribution_review.sh`

**Lines 563 and 566** — append `|| true` to both grep pipelines so a "no match" result doesn't trigger `set -e`:

```bash
# Line 563 (active tasks search):
found=$(grep -rl "^issue:.*/$issue_num$" "$TASK_DIR"/ 2>/dev/null | head -1 || true)

# Line 566 (archived tasks search):
found=$(grep -rl "^issue:.*/$issue_num$" "$ARCHIVED_DIR"/ 2>/dev/null | head -1 || true)
```

### Step 2: Verify

```bash
./.aitask-scripts/aitask_contribution_review.sh check-imported 6
# Expected output: NOT_IMPORTED

./.aitask-scripts/aitask_contribution_review.sh check-imported 999
# Expected output: NOT_IMPORTED

shellcheck .aitask-scripts/aitask_contribution_review.sh
```

### Step 3: Post-Implementation (Step 9)

Commit, archive task, push.

## Final Implementation Notes
- **Actual work done:** Added `|| true` to both grep pipelines in `cmd_check_imported()` (lines 563 and 566), exactly as planned.
- **Deviations from plan:** None.
- **Issues encountered:** None — the fix was straightforward.
- **Key decisions:** Used `|| true` rather than restructuring the function, as it's the minimal and idiomatic bash fix for grep-in-pipefail contexts.
