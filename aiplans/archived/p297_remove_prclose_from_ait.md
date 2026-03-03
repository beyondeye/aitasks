---
Task: t297_remove_prclose_from_ait.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

## Context

The `aitask_pr_close.sh` script is an internal script used only by skills (during archival in Step 9). It should not be exposed to users via the `ait` dispatcher's help text or command routing.

## Plan

1. **Remove `pr-close` from help text** in `ait` (line 39):
   - Delete the line `  pr-close       Close/decline linked pull requests`

2. **Remove `pr-close` dispatch case** in `ait` (line 134):
   - Delete the line `    pr-close)     shift; exec "$SCRIPTS_DIR/aitask_pr_close.sh" "$@" ;;`

## Files to modify

- `ait` (lines 39, 134)

## Verification

- Run `./ait help` and confirm `pr-close` no longer appears
- Run `./ait pr-close` and confirm it shows "unknown command"
- Verify `aitask_pr_close.sh` still exists (it's still used internally by skills)

## Final Implementation Notes
- **Actual work done:** Removed `pr-close` from both the help text and the command dispatch case in the `ait` dispatcher script, exactly as planned.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Only removed dispatcher exposure; the underlying `aitask_pr_close.sh` script remains untouched for internal skill use.
