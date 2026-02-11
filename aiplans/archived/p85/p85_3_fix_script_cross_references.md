---
Task: t85_3_fix_script_cross_references.md
Parent Task: aitasks/t85_universal_install.md
Sibling Tasks: aitasks/t85/t85_4_*.md, aitasks/t85/t85_5_*.md, etc.
Archived Sibling Plans: aiplans/archived/p85/p85_*_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Plan: t85_3 - Fix Script Cross-References

## Context

The aitask bash scripts were moved from the project root to `aiscripts/` in t85_1. Some scripts call other scripts using `./aitask_*.sh` paths which break because the `ait` dispatcher `cd`s to the project root, not `aiscripts/`. These functional cross-references must use `$SCRIPT_DIR` instead.

All work is in `~/Work/aitasks/aiscripts/`.

## Changes

### 1. `aiscripts/aitask_create.sh` — Add SCRIPT_DIR + fix 4 references

**Add** `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` near top (after `set -euo pipefail`, before `TASK_DIR`).

**Fix functional calls** (NOT help text examples):
- Line 214: `./aitask_ls.sh` → `"$SCRIPT_DIR/aitask_ls.sh"`
- Line 536: `./aitask_ls.sh` → `"$SCRIPT_DIR/aitask_ls.sh"`
- Line 268: `"./aitask_update.sh"` → `"$SCRIPT_DIR/aitask_update.sh"`
- Line 269: `./aitask_update.sh` → `"$SCRIPT_DIR/aitask_update.sh"`

### 2. `aiscripts/aitask_update.sh` — Add SCRIPT_DIR + fix 2 references

**Add** `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` near top.

**Fix functional calls:**
- Line 676: `./aitask_ls.sh` → `"$SCRIPT_DIR/aitask_ls.sh"`
- Line 745: `./aitask_ls.sh` → `"$SCRIPT_DIR/aitask_ls.sh"`

### 3. `aiscripts/aitask_board.sh` — Fix Python path

- Line 35: `aitask_board/aitask_board.py` → `board/aitask_board.py`

## Verification

1. `grep -n 'SCRIPT_DIR' ~/Work/aitasks/aiscripts/aitask_create.sh` — shows new definition
2. `grep -n '\./aitask_' ~/Work/aitasks/aiscripts/aitask_create.sh` — only help text matches remain
3. `grep -n '\./aitask_' ~/Work/aitasks/aiscripts/aitask_update.sh` — only help text matches remain
4. `grep 'board/aitask_board.py' ~/Work/aitasks/aiscripts/aitask_board.sh` — shows corrected path

## Final Implementation Notes
- **Actual work done:** Added `SCRIPT_DIR` definition to `aitask_create.sh` and `aitask_update.sh`. Fixed 4 cross-references in `aitask_create.sh` (2 to `aitask_ls.sh`, 2 to `aitask_update.sh`) and 2 in `aitask_update.sh` (both to `aitask_ls.sh`). Fixed `aitask_board.sh` Python path from `aitask_board/` to `board/`.
- **Deviations from plan:** None — task description line numbers for `aitask_update.sh` were slightly off (676/745 vs listed 657/726) but the correct lines were identified and fixed.
- **Issues encountered:** None.
- **Key decisions:** Only functional cross-script calls were fixed; help text examples (which show `./aitask_create.sh` usage) were left unchanged since they're documentation, not executable paths.
- **Notes for sibling tasks:** All scripts now properly use `SCRIPT_DIR` for cross-script calls. The pattern is: `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` at the top, then `"$SCRIPT_DIR/other_script.sh"` for calls. `TASK_DIR="aitasks"` remains a relative path and works because the `ait` dispatcher `cd`s to the project root. `aitask_board.sh` already had SCRIPT_DIR; `aitask_issue_import.sh` already uses `$SCRIPT_DIR/aitask_create.sh`; `aitask_ls.sh`, `aitask_stats.sh`, `aitask_clear_old.sh`, `aitask_issue_update.sh` are standalone with no cross-script calls.

## Post-Implementation (Step 9)

Archive child task and plan, update parent's `children_to_implement`.
