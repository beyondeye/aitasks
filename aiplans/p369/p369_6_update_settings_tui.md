---
Task: t369_6_update_settings_tui.md
Parent Task: aitasks/t369_aitask_explain_for_aitask_pick.md
Sibling Tasks: aitasks/t369/t369_*_*.md
Archived Sibling Plans: aiplans/archived/p369/p369_*_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: Update Settings TUI for gather_explain_context (t369_6)

## Overview

Add the `gather_explain_context` profile field to the settings TUI so it appears when viewing/editing execution profiles. This requires changes to three data structures in `settings_app.py`.

**Dependency:** Requires t369_3 (profile schema changes) to be completed.

## File to Modify

**`.aitask-scripts/settings/settings_app.py`** -- Three specific locations within this file.

## Detailed Implementation Steps

### Step 1: Add to PROFILE_SCHEMA

**Location:** The `PROFILE_SCHEMA` dict, around lines 86-106.

Find the line:
```python
    "post_plan_action": ("enum", ["start_implementation"]),
```

Add after it (or after `"abort_revert_status"` if that's the last entry -- insert it with the other planning-related fields):

```python
    "gather_explain_context": ("enum", ["ask", "0", "1", "2", "3", "5"]),
```

**Rationale:** Using `"enum"` type because the TUI presents enums as a selection list. The string values `"ask"`, `"0"`, `"1"`, etc. cover all common use cases. Users wanting other values (e.g., `"10"`) can edit the YAML file directly.

### Step 2: Add to PROFILE_FIELD_INFO

**Location:** The `PROFILE_FIELD_INFO` dict, around lines 137-260.

Find the entry for `"post_plan_action"` (or `"abort_revert_status"` if adding at the end of the planning section). Add:

```python
    "gather_explain_context": (
        "Historical plan context: 0 = off, N = max plans, ask = prompt",
        "Controls whether and how many historical plans are extracted during planning (Step 0a-bis):\n"
        "  'ask': prompt the user for the number of plans to extract\n"
        "  '0': disabled -- skip historical context gathering entirely\n"
        "  '1'-'5': extract at most N plans, greedily ordered by affected line count\n"
        "  (unset): treated as 'ask' -- the user is prompted\n"
        "Historical plans provide architectural context about why existing code was "
        "designed a certain way, helping the agent make better-informed decisions."
    ),
```

### Step 3: Add to PROFILE_FIELD_GROUPS

**Location:** The `PROFILE_FIELD_GROUPS` list, around line 263-275.

Find the "Planning" group:
```python
    ("Planning", ["plan_preference", "plan_preference_child", "post_plan_action"]),
```

Change to:
```python
    ("Planning", ["plan_preference", "plan_preference_child", "post_plan_action", "gather_explain_context"]),
```

### Step 4: Verify no other changes needed

Check if any validation logic in the TUI needs updating:
- The TUI uses `PROFILE_SCHEMA` for type checking and value validation
- The `"enum"` type is already handled by existing code
- No new widget types are needed since `"enum"` fields use the existing selection dialog

## Verification

1. **Syntax check:**
   ```bash
   python3 -c "import py_compile; py_compile.compile('.aitask-scripts/settings/settings_app.py', doraise=True)"
   ```

2. **Visual check:** Launch the TUI:
   ```bash
   ./ait settings
   ```
   Navigate to Profiles tab (press `p`), select a profile, and verify:
   - `gather_explain_context` appears in the "Planning" group
   - Pressing Enter/Space on it shows the enum options: ask, 0, 1, 2, 3, 5
   - Pressing `?` toggles between short and detailed descriptions

3. **Edit test:** Change the value, save, re-open, verify it persisted

4. **New profile test:** Verify `fast_with_historical_ctx.yaml` (from t369_3) shows the field with value `1`

## Step 9: Post-Implementation

Follow `.claude/skills/task-workflow/SKILL.md` Step 9 for cleanup, archival, and merge.
