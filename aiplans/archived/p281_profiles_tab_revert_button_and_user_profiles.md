---
Task: t281_profiles_tab_revert_button_and_user_profiles.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

# Implementation Plan: t281 — Profiles Tab Revert Button and User Profiles

## Context

The Profiles tab in `ait settings` currently supports project-level profiles only (git-tracked in `aitasks/metadata/profiles/`). Users can create, edit, save, and delete profiles, but there is no way to revert unsaved changes without leaving the tab, no clarification that profiles are project-scoped, and no support for user-local profiles. This task adds all three capabilities.

## Files to Modify

| File | Changes |
|------|---------|
| `aiscripts/settings/settings_app.py` | Revert button, layer badges, ConfigManager updates, NewProfileScreen scope selector |
| `aiscripts/aitask_scan_profiles.sh` | Scan both `profiles/` and `profiles/local/`, output `local/` prefix for user profiles |
| `.aitask-data/.gitignore` | Add `aitasks/metadata/profiles/local/` |
| `aiscripts/aitask_setup.sh` | Add gitignore entry for new installs |
| `tests/test_scan_profiles.sh` | Add tests for local profile scanning |

## Steps

1. Update explanation text with PROJECT/USER color-coded labels
2. Add `LOCAL_PROFILES_DIR` constant
3. Update ConfigManager: `profile_layers` dict, `load_profiles()` scans both dirs, `save_profile()` with layer param, `delete_profile()` method
4. Add layer badges to profile header and ConfigRow fields
5. Add Revert button + handler + `_revert_profile()` method
6. Make save/delete layer-aware
7. Update NewProfileScreen with scope selector
8. Update scanner script to scan both dirs and output `local/<filename>` for user profiles
9. Update gitignore files (data branch + setup script)
10. Add tests for local profile scanning
11. Create follow-up task for skill updates

## Post-Review Changes

### Change Request 1 (2026-03-02 14:45)
- **Requested by user:** Remove color-coded [PROJECT]/[USER] badges — too confusing. Instead show `local/<filename>` path for user profiles in the "Editing:" line and add descriptive scope text.
- **Changes made:** Replaced color badges with plain text: user profiles show `(local/fast.yaml)  (user-scoped, local only)`, project profiles show `(fast.yaml)  (project-scoped, shared with team)`. Updated explanation text to use plain text instead of colored badges. Reverted ConfigRow back to always using "project" layer since scope is communicated via the header line.
- **Files affected:** `aiscripts/settings/settings_app.py`

## Final Implementation Notes
- **Actual work done:** All 11 steps implemented as planned — revert button, explanation text, user-local profiles with `profiles/local/` directory, scanner script with `local/` prefix output, gitignore updates, tests, and follow-up task t282 created.
- **Deviations from plan:** Color-coded [PROJECT]/[USER] badges replaced with plain-text scope descriptions per user feedback. The "Editing:" header now shows `(local/fast.yaml) (user-scoped, local only)` or `(fast.yaml) (project-scoped, shared with team)` instead of colored badges. ConfigRow fields always use the "project" style since scope is communicated via header.
- **Issues encountered:** Test 16 initially had a wrong assertion checking for `PROFILE|custom.yaml|...` when the correct output is `PROFILE|local/custom.yaml|...` — fixed immediately.
- **Key decisions:** Scanner outputs `local/<filename>` as the filename field rather than adding a 5th layer field, so callers can resolve paths with `cat aitasks/metadata/profiles/<returned_filename>` naturally.

## Post-Implementation

See Step 9 in task-workflow SKILL.md for archival, merge, and cleanup.
