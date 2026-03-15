---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [contribution_review]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-15 14:56
updated_at: 2026-03-15 14:56
---

## Problem

The `check-imported` subcommand in `aitask_contribution_review.sh` exits with code 1 when no matching task is found, instead of outputting `NOT_IMPORTED`.

## Root Cause

`cmd_check_imported()` (lines 563, 566) uses `grep -rl ... | head -1` inside command substitutions. When `grep` finds no matches it returns exit code 1. With `set -euo pipefail` active, the non-zero exit code propagates through the pipeline and causes the script to abort immediately.

## Fix

Append `|| true` to both grep pipelines in `cmd_check_imported()` so that a "no match" result doesn't trigger `set -e`:

```bash
found=$(grep -rl "^issue:.*/$issue_num$" "$TASK_DIR"/ 2>/dev/null | head -1 || true)
```

Same fix needed for the `$ARCHIVED_DIR` grep on line 566.

## Files

- `.aitask-scripts/aitask_contribution_review.sh` — `cmd_check_imported()` function (lines 558-574)
