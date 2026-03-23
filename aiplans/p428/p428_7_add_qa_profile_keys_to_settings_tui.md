---
Task: t428_7_add_qa_profile_keys_to_settings_tui.md
Parent Task: aitasks/t428_new_skill_aitask_qa.md
Sibling Tasks: aitasks/t428/t428_5_*.md
Archived Sibling Plans: aiplans/archived/p428/p428_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Plan: Add qa_mode and qa_run_tests to Settings TUI

## Overview

Add two execution profile keys (`qa_mode` and `qa_run_tests`) introduced by the `/aitask-qa` skill (t428_1) to the settings TUI so they can be edited via `ait settings` in the Profiles tab.

## Steps

### 1. Add to `PROFILE_SCHEMA` (~line 108)

Add after `abort_revert_status`:
- `qa_mode` as enum with options: `["ask", "create_task", "implement", "plan_only"]`
- `qa_run_tests` as bool

### 2. Add to `PROFILE_FIELD_INFO` (~line 275)

Add short + detailed descriptions for both keys, following the existing pattern.

### 3. Add to `PROFILE_FIELD_GROUPS` (~line 285)

Add new group `("QA Analysis", ["qa_mode", "qa_run_tests"])` after "Post-Implementation".

## Final Implementation Notes

- **Actual work done:** Added `qa_mode` (enum) and `qa_run_tests` (bool) to all three profile data structures in `settings_app.py` exactly as planned.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Placed QA Analysis group after Post-Implementation and before Exploration in the field groups, which follows logical workflow ordering.
- **Notes for sibling tasks:** The three profile data structures (`PROFILE_SCHEMA`, `PROFILE_FIELD_INFO`, `PROFILE_FIELD_GROUPS`) are the standard locations for adding any new profile key to the TUI. Follow the same pattern for future profile keys.
