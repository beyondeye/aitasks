---
Task: t211_aitask_stats_macos_compat.md
Worktree: N/A (working on current branch)
Branch: N/A (working on current branch)
Base branch: main
---

# Plan: Fix aitask_stats macOS Compatibility (t211)

## Context

`aitask_stats.sh` and other scripts fail on macOS due to two issues: (1) `#!/bin/bash` shebang resolves to system bash 3.2 which lacks `declare -A`, `local -n`, `${var^}`, and (2) `date -d` is GNU-only. Setup already installs brew bash 5.x and coreutils (gdate) but scripts don't use them.

## Changes

### 1. Fix shebangs (20 files): `#!/bin/bash` → `#!/usr/bin/env bash`
### 2. Add `portable_date()` wrapper to `terminal_compat.sh`
### 3. Replace `date -d` in `aitask_stats.sh` (14) and `aitask_issue_import.sh` (1)
### 4. Add tests and update documentation

## Verification
- [x] Run aitask_stats.sh — works, shows 182 completed tasks
- [x] Run all tests — 34/34 sed_compat tests pass, no regressions
- [x] Pre-existing test failures unchanged (draft_finalize, global_shim, setup_git, t167_integration)

## Final Implementation Notes
- **Actual work done:** Fixed 20 shebangs, added `portable_date()` wrapper, replaced 16 `date -d` calls, added 6 portable_date tests, updated documentation.
- **Deviations from plan:** `aitask_stats.sh` needed `source terminal_compat.sh` added since it didn't source it previously. The `date -d` count was 15 in stats + 1 in issue_import = 16 total (plan said 14+1).
- **Issues encountered:** The global `replace_all` for `date -d ` ate the space before the quote, requiring a second pass to restore `portable_date -d "` spacing.
- **Key decisions:** Used `gdate` on macOS (already installed by `ait setup`) rather than rewriting date logic with BSD date syntax. This is simpler and the dependency already exists.
