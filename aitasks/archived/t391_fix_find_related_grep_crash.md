---
priority: high
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_contribute]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-15 15:44
updated_at: 2026-03-15 15:44
---

# Fix grep pipefail crash in contribution-review find-related

## Problem

`aitask_contribution_review.sh find-related <N>` crashes silently with exit code 1 when the target issue body contains no `#N` references (e.g., issue #5).

## Root Cause

In `parse_linked_issues()` (line 367), the pipeline:

```bash
echo "$text" | grep -oE '#[0-9]+' | sed 's/^#//' | sort -un | while read -r num; do
```

When `grep -oE '#[0-9]+'` finds no matches, it returns exit code 1. With `set -euo pipefail`, this propagates through the pipeline, causing the function to return 1. The calling code at line 424 (`candidate_nums=$(parse_linked_issues ...)`) then triggers `set -e` and the script exits immediately.

Other grep calls in the same file already handle this pattern correctly (e.g., `|| echo ""` on lines 326 and 335).

## Fix

Wrap the grep to tolerate no-match:

```bash
echo "$text" | { grep -oE '#[0-9]+' || true; } | sed 's/^#//' | sort -un | while read -r num; do
```

## Files

- `.aitask-scripts/aitask_contribution_review.sh` — `parse_linked_issues()` function (line ~367)
