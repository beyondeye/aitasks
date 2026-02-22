---
Task: t208_version_checks_setup_macos.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Added version validation for Bash (>= 4.0) and Python (>= 3.9) to `ait setup`, with automatic upgrade via Homebrew on macOS. Fixed a Python < 3.10 compatibility issue in the board TUI. Documented Homebrew as a macOS prerequisite across all installation documentation.

## Files Modified

- **aiscripts/aitask_setup.sh** — Added `check_bash_version()` function (~45 lines) that checks `BASH_VERSINFO >= 4.0`, locates brew-installed bash on macOS, and prints PATH/chsh instructions. Added `check_python_version()` function (~55 lines) that validates Python >= 3.9, offers `brew install python@3` on macOS, and sets `PYTHON_VERSION_OK` flag. Modified `setup_python_venv()` to auto-install Python via brew if missing, call version check, and recreate venv if existing Python is too old. Updated `main()` to call `check_bash_version` after `install_cli_tools` and show versions in summary.
- **aiscripts/board/aitask_board.py** — Added `from __future__ import annotations` to fix `bool | None` type union syntax that requires Python 3.10+ at runtime.
- **README.md** — Added macOS prerequisite callout before Quick Install section.
- **website/content/docs/installation/_index.md** — Added macOS Homebrew prerequisite note.
- **website/content/docs/getting-started.md** — Added macOS Homebrew prerequisite note before `ait setup` step.
- **website/content/docs/commands/setup-install.md** — Made Homebrew explicit in CLI tools step, added version checks step, renumbered subsequent steps, noted venv recreation.
- **tests/test_version_checks.sh** (new) — 8 tests covering bash version check on current shell, python version parsing (3.12 pass, 3.8 fail, 3.9 boundary pass, 2.7 fail, broken python, macOS path).

## Probable User Intent

macOS users running `ait board` were hitting a `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` error because `bool | None` type hints require Python 3.10+. More broadly, macOS ships Bash 3.2 and may have old/no Python 3, causing cryptic failures when running aitask commands. The intent is to catch these version issues early during `ait setup` with clear messages and automatic remediation via Homebrew, rather than letting users hit confusing runtime errors later.

## Final Implementation Notes

- **Actual work done:** All version check functions, setup integration, board fix, documentation updates, and tests implemented.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed)
- **Issues encountered:** N/A (changes were already made before wrapping)
- **Key decisions:** Version check functions are deliberately Bash 3.2-compatible since they run under macOS default bash during initial setup. `check_bash_version` warns but does not die, since `aitask_setup.sh` itself works under 3.2. `check_python_version` uses a global `PYTHON_VERSION_OK` flag rather than stdout to communicate results, avoiding subshell issues.
