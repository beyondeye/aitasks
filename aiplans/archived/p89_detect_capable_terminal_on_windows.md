---
Task: t89_detect_capable_terminal_on_windows.md
Worktree: (none - working on main branch)
Branch: main
Base branch: main
---

# Plan: t89 — Detect Capable Terminal on Windows/WSL

## Context

The aitasks scripts use TUI features (fzf, colors, Python textual board) that work well in modern terminals but poorly in the legacy Windows Console Host (conhost.exe). When WSL users launch scripts from conhost.exe, they get glitchy rendering, no true color, and broken Unicode. This task adds a detection check that warns users and suggests fixes.

## Approach

Create a shared library `aiscripts/lib/terminal_compat.sh` with terminal capability detection. Interactive scripts source it and call the check before using TUI features. The check warns but does not block execution.

## Implementation

### New files
- `aiscripts/lib/terminal_compat.sh` — shared library with terminal detection, color defs, helpers
- `tests/test_terminal_compat.sh` — 36 automated tests

### Modified files
- `aiscripts/aitask_create.sh` — source lib, remove duplication, add terminal check in main()
- `aiscripts/aitask_update.sh` — source lib, remove duplication, add terminal check in run_interactive_mode()
- `aiscripts/aitask_issue_import.sh` — source lib, remove duplication, add terminal check in run_interactive_mode()
- `aiscripts/aitask_board.sh` — source lib, add terminal check before exec Python
- `aiscripts/aitask_clear_old.sh` — source lib, remove duplication (no terminal check)
- `aiscripts/aitask_issue_update.sh` — source lib, remove duplication (no terminal check)
- `install.sh` — updated set_permissions() to include aiscripts/lib/

### Not modified
- `aitask_setup.sh` — runs before lib exists; has own helpers
- `aitask_ls.sh`, `aitask_stats.sh` — no TUI features
- `ait` dispatcher — uses exec
- `board/aitask_board.py` — bash wrapper handles check

## Final Implementation Notes
- **Actual work done:** Created shared library with 5-level terminal detection (COLORTERM, WT_SESSION, TERM_PROGRAM, TERM, TMUX/STY), WSL-specific warnings, and suppression via AIT_SKIP_TERMINAL_CHECK=1. Deduplicated ~85 lines of color/helper code across 6 scripts. Added comprehensive test suite with 36 tests.
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** Initial test script had a bug where `assert_capable` reset the cache before testing cached values. Fixed by using inline test code for caching tests instead of the helper function.
- **Key decisions:**
  - Library warns but never blocks (returns 0 always)
  - Check runs every time (not just at install) since terminal host can change between sessions
  - Batch mode scripts skip the check entirely (no warning in CI/automation)
  - `aitask_setup.sh` intentionally NOT changed — it runs during first install before the lib exists
