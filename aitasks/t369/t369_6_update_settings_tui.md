---
priority: low
effort: low
depends: [t369_5]
issue_type: feature
status: Ready
labels: [aitask_explain, settings]
created_at: 2026-03-11 18:34
updated_at: 2026-03-11 18:34
---

Add gather_explain_context field to the ait settings TUI (settings_app.py). Add to PROFILE_SCHEMA (int_or_ask type), PROFILE_FIELD_INFO, and PROFILE_FIELD_GROUPS (Planning group).

## Context

The settings TUI (`.aitask-scripts/settings/settings_app.py`) provides a graphical interface for editing execution profiles. When t369_3 adds the `gather_explain_context` key to profile files, the TUI needs to know about this field so users can view and edit it. Without this update, the field would be invisible in the TUI (though it would still work in profile YAML files).

The TUI uses three data structures to define profile fields:
1. `PROFILE_SCHEMA` -- defines the type and valid options for each field
2. `PROFILE_FIELD_INFO` -- provides short and detailed descriptions
3. `PROFILE_FIELD_GROUPS` -- organizes fields into logical groups for display

## Key Files to Modify

- **`.aitask-scripts/settings/settings_app.py`** -- Add the new field to three data structures.

## Reference Files for Patterns

- **`.aitask-scripts/settings/settings_app.py`** -- The file being modified. Key locations:
  - `PROFILE_SCHEMA` dict (line ~86): defines `(type, options)` tuples. Existing types are `"bool"`, `"enum"`, `"string"`. The new field needs a type that accepts both integers and the string `"ask"`. Use `"enum"` with options `["ask", "0", "1", "2", "3", "5"]` since the TUI presents enums as a selection list.
  - `PROFILE_FIELD_INFO` dict (line ~137): defines `(short_description, detailed_description)` tuples.
  - `PROFILE_FIELD_GROUPS` list (line ~263): organizes fields into named groups. The "Planning" group currently has `["plan_preference", "plan_preference_child", "post_plan_action"]`.

## Implementation Plan

### Step 1: Add to PROFILE_SCHEMA

In the `PROFILE_SCHEMA` dict (around line 86-106), add:
```python
"gather_explain_context": ("enum", ["ask", "0", "1", "2", "3", "5"]),
```

Insert it after the `"post_plan_action"` entry to keep it near the other planning-related fields.

Note: Using `"enum"` type with string representations of numbers. The TUI presents this as a selectable list. The values `"ask"`, `"0"`, `"1"`, `"2"`, `"3"`, `"5"` cover the common use cases. Users who want other values can edit the YAML directly.

### Step 2: Add to PROFILE_FIELD_INFO

In the `PROFILE_FIELD_INFO` dict (around line 137-260), add:
```python
"gather_explain_context": (
    "Historical plan context: 0 = off, N = max plans, ask = prompt",
    "Controls whether and how many historical plans are extracted during planning (Step 0a-bis):\n"
    "  'ask': prompt the user for the number of plans to extract\n"
    "  '0': disabled - skip historical context gathering entirely\n"
    "  '1'-'5': extract at most N plans, greedily ordered by affected line count\n"
    "  (unset): treated as 'ask' - the user is prompted\n"
    "Historical plans provide architectural context about why existing code was "
    "designed a certain way, helping the agent make better-informed decisions."
),
```

Insert it after the `"post_plan_action"` entry (or `"post_plan_action_for_child"` if that exists in the dict).

### Step 3: Add to PROFILE_FIELD_GROUPS

In the `PROFILE_FIELD_GROUPS` list (around line 263), find the "Planning" group:
```python
("Planning", ["plan_preference", "plan_preference_child", "post_plan_action"]),
```

Change it to:
```python
("Planning", ["plan_preference", "plan_preference_child", "post_plan_action", "gather_explain_context"]),
```

## Verification Steps

1. **Syntax check**: `python3 -c "import py_compile; py_compile.compile('.aitask-scripts/settings/settings_app.py', doraise=True)"` -- verify no syntax errors.
2. **Visual check**: Launch the TUI with `python3 .aitask-scripts/settings/settings_app.py` (or `./ait settings`), navigate to the Profiles tab, edit a profile, and verify `gather_explain_context` appears in the Planning group with the correct options.
3. **Edit test**: Select a profile, change `gather_explain_context` to `"1"`, save, and verify the YAML file is updated correctly.
4. **Description toggle**: Press `?` on the field and verify both short and detailed descriptions appear.
