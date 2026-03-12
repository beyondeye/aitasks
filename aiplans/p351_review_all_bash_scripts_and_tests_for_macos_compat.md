---
Task: t351_review_all_bash_scripts_and_tests_for_macos_compat.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: t351 — Review All Bash Scripts and Tests for macOS Compatibility

## Context

The aitasks framework has grown significantly since the last macOS compatibility audit (t209, t211, t213). There are now 43 test files and ~18+ shell scripts. This task verifies everything still passes on macOS and fixes any regressions.

Static analysis by explore agents found the codebase is in **good shape** — no `grep -P`, no raw `sed -i`, no `mktemp --suffix`, correct shebangs everywhere. Bash 4+ features (`declare -A`, `${var^}`, `local -n`) are safe because `#!/usr/bin/env bash` picks up brew bash 5.x.

## Plan

### Step 1: Run All Tests on macOS

Run all 43 tests in batches, capturing pass/fail for each.

### Step 2: Run Shellcheck

Focus on errors only.

### Step 3: Fix Any Failures

### Step 4: Re-run Failing Tests to Verify Fixes

### Step 5: Post-Implementation (Step 9)

## Key Files

- `.aitask-scripts/lib/terminal_compat.sh` — compatibility helpers
- `.aitask-scripts/lib/task_utils.sh` — shared utilities
- `aidocs/sed_macos_issues.md` — documented macOS issues
- `tests/test_sed_compat.sh` — dedicated macOS compat test

## Final Implementation Notes

- **Actual work done:** Ran all 42 tests (skipped test_codex_model_detect which requires API keys), ran shellcheck (0 errors). Found and fixed 2 macOS-specific issues + 3 test maintenance issues.
- **Deviations from plan:** No deviations. All steps executed as planned.
- **Issues encountered:**
  1. **macOS BSD awk multiline variable** — `insert_aitasks_instructions()` in `aitask_setup.sh` passed multi-line content via `awk -v block=...`. BSD awk (macOS default) warns "newline in string" and corrupts output. Fixed by using `ENVIRON["_awk_block"]` instead. Affected: test_agent_instructions.sh (crash), test_data_branch_setup.sh (1 failure).
  2. **Python 3.10+ type syntax** — `aitask_codemap.py` used `str | None` union syntax requiring Python 3.10+, but macOS system Python is 3.9.6. Fixed by adding `from __future__ import annotations`. Affected: test_contribute.sh (18 codemap failures).
  3. **`_AIT_SHIM_ACTIVE` environment leak** — `test_global_shim.sh` failed because the shim recursion guard variable leaked from the parent ait process. Fixed by adding `unset _AIT_SHIM_ACTIVE` at test start.
  4. **Stale skill counts** — test_opencode_setup.sh (expected 17 skills, now 18) and test_gemini_setup.sh (expected 18 policy entries, now 19). Updated counts.
  5. **Wrong assertion keyword** — test_opencode_setup.sh checked for "Skills" in opencode Layer 2 seed, but the file contains "Agent Identification". Fixed assertion.
- **Key decisions:** Used `ENVIRON` approach for awk multiline fix (cleaner than temp files). Used `from __future__ import annotations` for Python compat (avoids touching every type annotation).
- **Shellcheck:** 0 errors across all scripts. 63 warnings (style only: SC2034, SC2046, SC2155), not in scope.
