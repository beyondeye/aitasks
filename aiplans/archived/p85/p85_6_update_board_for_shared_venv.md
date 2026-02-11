---
Task: t85_6_update_board_for_shared_venv.md
Parent Task: aitasks/t85_universal_install.md
Sibling Tasks: aitasks/t85/t85_7_*.md, aitasks/t85/t85_8_*.md, etc.
Archived Sibling Plans: aiplans/archived/p85/p85_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t85_6 - Update aitask_board.sh for Shared Venv

## Context

The `aitask_board.sh` script currently auto-installs Python dependencies via pip/pipx/pacman when they're missing. As part of the aitask framework distribution (t85), dependency management was centralized into `ait setup` which creates a shared venv at `~/.aitask/venv/`. This task replaces the auto-install logic with venv-first resolution.

## File to Modify

- `~/Work/aitasks/aiscripts/aitask_board.sh` — replace entire content after the shebang/SCRIPT_DIR lines

## Implementation

Replace the script contents with the new version from the task spec:

1. Keep `SCRIPT_DIR` definition (already present)
2. Add `VENV_PYTHON="$HOME/.aitask/venv/bin/python"`
3. If venv python exists and is executable, use it directly (no dependency checks needed)
4. Otherwise fall back to system python with dependency checks but **no auto-install** — just error with `ait setup` instructions
5. `exec "$PYTHON"` with proper quoting

### Key changes from current version
- **Prefers `~/.aitask/venv/bin/python`** — uses shared venv directly
- **Falls back to system python** with dependency checks but does NOT auto-install
- **Removes all auto-install logic** (pip, pipx, pacman) — delegates to `ait setup`
- **Error messages reference `ait setup`**
- **Quotes `$PYTHON`** in the `exec` line

## Verification

1. With venv present: `cd ~/Work/aitasks && ./ait board --help` or similar launches using venv python
2. Check no references to `pacman`, `pipx`, or `pip install` remain: `grep -E 'pacman|pipx|pip install' ~/Work/aitasks/aiscripts/aitask_board.sh`
3. Verify `ait setup` is referenced in error messages: `grep 'ait setup' ~/Work/aitasks/aiscripts/aitask_board.sh`
4. Syntax check: `bash -n ~/Work/aitasks/aiscripts/aitask_board.sh`

## Final Implementation Notes
- **Actual work done:** Replaced `aitask_board.sh` (35→31 lines). Added `VENV_PYTHON` variable, venv-first resolution with system python fallback, removed all auto-install logic (pip, pipx, pacman), updated error messages to reference `ait setup`, and properly quoted `$PYTHON` in `exec`.
- **Deviations from plan:** None — implementation exactly matches the task spec.
- **Issues encountered:** None. All verification checks passed: syntax check, no auto-install references, `ait setup` in error messages, and functional TUI board launch with venv.
- **Key decisions:** Kept the `"Or install manually: pip install ${missing[*]}"` hint in the fallback error message as a convenience for users who prefer not to use `ait setup`.
- **Notes for sibling tasks:** The board script now follows the same venv-first pattern established by t85_5. Any future Python-using scripts should check `$HOME/.aitask/venv/bin/python` first and fall back to system python with dependency checks (but no auto-install).

## Post-Implementation (Step 9)

Archive child task and plan, update parent's `children_to_implement`.
