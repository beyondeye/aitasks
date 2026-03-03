---
Task: t306_auto_update_pick_the_wrong_version.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The auto-update check in `ait` suggests "Update available: 0.8.0 → 0.7.1" — a downgrade.

**Root cause chain:**
1. ~13h ago, the cache (`~/.aitask/update_check`) was populated via the GitHub API. At that time, the latest release was v0.7.1.
2. The v0.8.0 release was published to GitHub after the cache was populated.
3. The VERSION file was already bumped to 0.8.0 locally (commit `f9ccb9a`).
4. When `ait` runs, the cache is < 24h old ("fresh"), so it uses the stale cached version 0.7.1.
5. The comparison on line 87 of `ait` is `if [[ "$local_version" != "$cached_version" ]]` — pure string inequality with no directionality check.
6. Result: `0.8.0 != 0.7.1` is true → shows downgrade suggestion.

The GitHub API parsing (`sed` command) works correctly and returns `0.8.0` now. The issue is the missing semver comparison.

## Implementation Steps

- [x] 1. Add `version_gt` helper function to `ait` before `check_for_updates()`
- [x] 2. Change line 87 comparison from string inequality to semver comparison
- [x] 3. Verify with shellcheck and manual tests

## Verification

- Clear cache and test: `echo "$(date +%s) 0.7.1" > ~/.aitask/update_check` then run `./ait ls` — should NOT show update (0.7.1 < 0.8.0)
- Test upgrade case: `echo "$(date +%s) 0.9.0" > ~/.aitask/update_check` then run `./ait ls` — should show update
- Test equal: `echo "$(date +%s) 0.8.0" > ~/.aitask/update_check` then run `./ait ls` — should NOT show update
- Run `shellcheck ait`

## Final Implementation Notes
- **Actual work done:** Added `version_gt()` semver comparison function and replaced string inequality check with proper version comparison in the auto-update logic
- **Deviations from plan:** None — implementation matched the plan exactly
- **Issues encountered:** None
- **Key decisions:** Used `SC2206` shellcheck disable for the word-splitting array assignment which is intentional (splitting version string on `.`)
