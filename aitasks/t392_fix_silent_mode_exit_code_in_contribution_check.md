---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_contribute]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-15 16:03
updated_at: 2026-03-15 16:04
---

## Problem

When running `aitask_contribution_check.sh` with `--dry-run --silent`, the script exits with code 1 despite producing valid output. Claude Code's bash tool reports this as an error, though the workflow continues.

## Root Cause

Line 840 in `.aitask-scripts/aitask_contribution_check.sh`:

```bash
[[ "$ARG_SILENT" != true ]] && success "Overlap analysis complete for issue #${ARG_ISSUE}."
```

When `--silent` is active, `[[ "true" != true ]]` evaluates to false (exit code 1). The `&&` short-circuits, making the entire expression exit code 1. Since this is the **last command** in `main()`, it becomes the script's exit code.

## Fix

Change line 840 from `[[ ]] && ...` pattern to an `if` statement:

```bash
if [[ "$ARG_SILENT" != true ]]; then
    success "Overlap analysis complete for issue #${ARG_ISSUE}."
fi
```

Other `[[ "$ARG_SILENT" != true ]] && ...` patterns in the script (lines 716, 733, 742, 745, 752, 811, 814, 832) are safe because they're not the last command in their execution path.

## Verification

```bash
./.aitask-scripts/aitask_contribution_check.sh 5 --dry-run --silent; echo "Exit code: $?"
```

Expected: exit code 0 with overlap analysis output.
