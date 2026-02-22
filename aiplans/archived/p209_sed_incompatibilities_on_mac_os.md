---
Task: t209_sed_incompatibilities_on_mac_os.md
Worktree: N/A (working on current branch)
Branch: N/A (working on current branch)
Base branch: main
---

# Plan: Fix macOS sed Incompatibilities (t209)

## Context

macOS ships with BSD sed, which differs from GNU sed in several ways. The aitasks framework has 7 lines across 4 files that use GNU-specific sed features, causing failures on macOS. Since only 7 lines out of ~75 total sed usages are problematic, we fix them in place rather than adding `gnu-sed` as a new brew dependency.

## Changes

### 1. Add `sed_inplace()` helper to `terminal_compat.sh`

**File:** `aiscripts/lib/terminal_compat.sh` (after `ait_is_wsl()`, before `ait_warn_if_incapable_terminal()`)

Add a portable wrapper for `sed -i` that detects macOS and uses `sed -i ''`.

### 2. Fix `aitask_archive.sh` — `archive_metadata_update()`

**File:** `aiscripts/aitask_archive.sh` lines 114-119

- Lines 114-115: Replace `sed -i` with `sed_inplace`
- Line 118: Replace GNU `sed -i "/pattern/a text"` with portable awk

### 3. Fix `aitask_create.sh` — line 275

Replace GNU `sed "/^labels:/a text"` with portable awk.

### 4. Fix `aitask_stats.sh` — `\U` uppercase

Lines 61 and 680: Replace GNU `sed 's/^./\U&/'` with bash 4.0+ `${var^}`.

### 5. Fix `task_utils.sh` — grouped multi-line sed commands

**File:** `aiscripts/lib/task_utils.sh` line 274

Replace `sed -e :a -e '/^[[:space:]]*$/{ $d; N; ba; }'` (BSD sed fails with `{` `}` across `-e` args) with portable awk for trailing blank line trimming.

### 6. Create `aidocs/sed_macos_issues.md` — reference documentation

### 7. Add sed warning to `CLAUDE.md`

## Verification

- [x] Run shellcheck on all 5 modified shell files — only pre-existing warnings
- [x] Run all existing tests — test_resolve_tar_gz.sh now passes (was failing due to BSD sed)
- [x] test_terminal_compat.sh passes (36/36)
- [x] test_sed_compat.sh passes (28/28) — new dedicated test suite

## Final Implementation Notes
- **Actual work done:** Fixed 7 GNU-specific sed usages across 4 shell scripts. Added `sed_inplace()` helper to `terminal_compat.sh`. Created reference documentation in `aidocs/sed_macos_issues.md` and added CLAUDE.md warning. Wrote 28 automated tests.
- **Deviations from plan:** Discovered an additional incompatibility in `task_utils.sh` line 274 (grouped `{ $d; N; ba; }` fails on BSD sed) that was not in the original plan. This was caught by `test_resolve_tar_gz.sh` which was failing on macOS. Added `test_sed_compat.sh` test suite (not originally planned but requested during review).
- **Issues encountered:** The `sed -i` portability issue has no single-syntax solution that works on both GNU and BSD sed, so a platform-detecting wrapper (`sed_inplace()`) was the chosen approach. The `a` (append) command syntax also differs, requiring awk as a portable alternative.
- **Key decisions:** Chose to fix in place rather than add `gnu-sed` as a brew dependency, since only 7 out of ~75 sed usages were problematic. Used `awk` for append-after-line and trailing-blank-line trimming. Used bash 4.0+ `${var^}` for uppercase (already a project requirement).
