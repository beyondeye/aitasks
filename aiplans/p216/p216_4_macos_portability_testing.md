---
Task: t216_4_macos_portability_testing.md
Parent Task: aitasks/t216_ait_board_out_of_sync_if_changes_from_other_pc.md
Sibling Tasks: aitasks/t216/t216_1_*.md, aitasks/t216/t216_2_*.md, aitasks/t216/t216_3_*.md
Archived Sibling Plans: aiplans/archived/p216/p216_*_*.md
---

# Implementation Plan: t216_4 — macOS Portability Testing

## Overview

Test `ait sync` on macOS to verify portability. Fix any issues found in `aiscripts/aitask_sync.sh` and `tests/test_sync.sh`.

## Test Checklist

1. **`timeout` command** — verify fallback watchdog works when `timeout` not in PATH
2. **`sed` portability** — verify BSD sed compat, use `sed_inplace()` if needed
3. **`grep` portability** — no `-P`, no `\K`, no lookahead/lookbehind
4. **`wc -l` padding** — arithmetic comparisons, not string
5. **`mktemp`** — no `--suffix`, use template pattern
6. **`base64`** — cross-platform decode if used
7. **Git operations** — verify rebase/push/pull on macOS git
8. **bash version** — no bash 4+ features (no `declare -A`, no `${var^}`)
9. **Run `bash tests/test_sync.sh`** — all tests pass on macOS

## Execution

Run on macOS machine. Fix any failures directly in the script/test files.

## Verification

- [ ] `shellcheck aiscripts/aitask_sync.sh` on macOS
- [ ] `bash tests/test_sync.sh` — all PASS on macOS
- [ ] `./ait sync --batch` and `./ait sync` manual test on macOS
- [ ] Timeout fallback test: `PATH` without `timeout`, run sync

## Post-Implementation (Step 9)

Archive t216_4, update parent children_to_implement.
