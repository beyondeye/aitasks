---
Task: t212_fix_macos_test_portability.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Fix 4 failing shell test scripts caused by macOS portability issues. Three distinct root causes were identified and fixed, plus documentation was added to the macOS compatibility guide.

## Files Modified

### tests/test_draft_finalize.sh, tests/test_setup_git.sh, tests/test_t167_integration.sh
- Added whitespace trimming (`xargs`) to `assert_eq()` helper function
- macOS `wc -l` pads output with leading spaces (e.g. `"       1"`), causing exact string comparisons to fail
- Fix applied at the `assert_eq` level so all future `wc -l` comparisons work automatically

### tests/test_t167_integration.sh
- Replaced hardcoded Linux path `/home/ddt/Work/TESTS/test_t167` with `$(mktemp -d)/test_t167`
- The original path was from the developer's Linux machine and fails on macOS (`mkdir -p /home/ddt` → "Operation not supported")

### tests/test_global_shim.sh
- Test 4 ("Setup non-interactive, no network") assumed `curl` would fail, but didn't mock network access
- On machines with internet, `curl` successfully downloads the real installer from GitHub, so the test got exit code 0 instead of expected 1
- Added fake `curl`/`wget` scripts that always `exit 1`, prepended to PATH during the test

### aidocs/sed_macos_issues.md
- Added new `## wc -l Output Whitespace` section documenting the macOS vs Linux difference
- Explains when it's safe (arithmetic contexts) vs when it breaks (string comparisons)
- Shows portable fixes: `tr -d ' '`, `xargs`, or trimming in helper functions

### CLAUDE.md
- Added one-line `wc -l portability` bullet under Shell Conventions, referencing the detailed docs

## Probable User Intent

Ensure all shell tests pass on macOS. The test failures were platform-specific bugs in the test harness, not in the production scripts (all 11 `wc -l` usages in `aiscripts/` use arithmetic contexts which auto-strip whitespace).

## Final Implementation Notes

- **Actual work done:** Fixed assert_eq in 3 test files, replaced hardcoded path, mocked network in shim test, documented wc -l gotcha
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed)
- **Issues encountered:** N/A (changes were already made before wrapping)
- **Key decisions:** Chose to fix at the `assert_eq` level rather than adding `| tr -d ' '` to each of 21 `wc -l` calls — single point of maintenance, future-proof
