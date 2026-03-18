---
Task: t416_review_scripts_for_macos_compat.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t416 — Review All Bash Scripts for macOS Compatibility

## Context

Since the last macOS compatibility audit (t351), ~22 new shell scripts and several Python files have been added. This review ensures all scripts follow macOS/BSD portability conventions. The audit covers all 128+ bash scripts and Python files that use type annotations.

## Audit Results Summary

**All 128 shell scripts are clean.** No macOS-incompatible patterns found:
- All shebangs use `#!/usr/bin/env bash` ✅
- No raw `sed -i` (all use `sed_inplace()`) ✅
- No `grep -P` or `-oP` ✅
- No `mktemp --suffix` ✅
- No `readarray`/`mapfile` ✅
- All `date -d` uses go through `portable_date()` or `date --version` checks ✅
- All `wc -l` in string comparisons use `| tr -d ' '` ✅
- `base64` decode uses platform detection ✅
- No problematic `awk -v` with multiline content ✅

**1 issue found:** 4 Python files in `.aitask-scripts/codebrowser/` use `str | None` union syntax (requires Python 3.10+) without `from __future__ import annotations`. macOS may have Python 3.9.

## Implementation Steps

### Step 1: Fix Python files — add `from __future__ import annotations`

Add `from __future__ import annotations` as the first import in each file:

1. `.aitask-scripts/codebrowser/code_viewer.py` — uses `int | None`, `tuple[int | None, int | None]`
2. `.aitask-scripts/codebrowser/codebrowser_app.py` — uses `dict | None`, `int | None`, `str | None`, `tuple[int, int] | None`
3. `.aitask-scripts/codebrowser/detail_pane.py` — uses `str | None`
4. `.aitask-scripts/codebrowser/explain_manager.py` — uses `str | None`

Same fix applied in t351 for `aitask_codemap.py`.

### Step 2: Run shellcheck

```bash
shellcheck .aitask-scripts/aitask_*.sh
```

Baseline check — not expected to find macOS-specific issues but good hygiene.

### Step 3: Run key tests

```bash
bash tests/test_sed_compat.sh
bash tests/test_terminal_compat.sh
```

### Step 4: Commit and archive

Commit message: `chore: Add future annotations to codebrowser Python files for macOS compat (t416)`

## Verification

- `python3 -c "from __future__ import annotations; import codebrowser.code_viewer"` (or similar import check)
- `bash tests/test_sed_compat.sh` passes
- `bash tests/test_terminal_compat.sh` passes
- `shellcheck .aitask-scripts/aitask_*.sh` — no new errors

## Final Implementation Notes
- **Actual work done:** Audited all 128+ bash scripts and Python files for macOS/BSD compatibility. Fixed 4 Python codebrowser files missing `from __future__ import annotations` (needed for `str | None` syntax on Python 3.9). All shell scripts were already clean.
- **Deviations from plan:** None — the fix was exactly as planned.
- **Issues encountered:** None. shellcheck showed only info-level warnings (SC1091 source following, SC2012 ls vs find) — all pre-existing and not macOS-related.
- **Key decisions:** The 4 codebrowser Python files were likely missed by t351 because they were added after that audit or weren't included in its scope.

## Post-Implementation (Step 9)

Archive t416 via `aitask_archive.sh`.
