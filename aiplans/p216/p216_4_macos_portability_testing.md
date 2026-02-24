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

- [x] `shellcheck aiscripts/aitask_sync.sh` on macOS — clean (only SC1091 info-level for sourced files)
- [x] `bash tests/test_sync.sh` — 34/34 PASS on macOS (Darwin 24.6.0, bash 5.3.9, aarch64)
- [x] `./ait sync --batch` manual test on macOS — returns NOTHING (correct)
- [x] Timeout fallback test: `PATH` without `timeout`, sync returns PUSHED (watchdog works)

## Portability Checklist Results

| Area | Status | Notes |
|------|--------|-------|
| `timeout` fallback | OK | Lines 92-118: background process watchdog with `kill -0`, `sleep 1` loop |
| `sed` usage | OK | Only `sed 's/,$//'` (basic, no `-i`) |
| `grep` usage | OK | No `-P`, no `\K`, no lookahead/lookbehind |
| `wc -l` padding | OK | Line 166: `wc -l \| tr -d ' '` (already portable) |
| `mktemp` | OK | Tests use `mktemp -d` only (no `--suffix`) |
| `base64` | N/A | Not used |
| Git operations | OK | Standard git commands, no version-specific flags |
| bash version | OK | No `declare -A`, no `${var^}`, no bash 4+ features |

## Final Implementation Notes

- **Actual work done:** Ran all verification checks from the task checklist on macOS (Darwin 24.6.0, aarch64, bash 5.3.9 via homebrew). All checks passed with zero issues found. No source code changes were needed.
- **Deviations from plan:** None — the plan was a pure verification/testing task and all checks passed as-is.
- **Issues encountered:** None. The sync script was written with macOS portability in mind from the start (per p216_1 implementation notes). The `_git_with_timeout()` fallback, `wc -l | tr -d ' '` pattern, and avoidance of GNU-only features all work correctly.
- **Key decisions:** No code changes required. The script is already portable.
- **Notes for sibling tasks:** All siblings are already archived. This was the final child task.

## Post-Implementation (Step 9)

Archive t216_4, update parent children_to_implement.
