---
priority: medium
effort: low
depends: []
issue_type: feature
status: Done
labels: [testing, qa, settings]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-22 12:05
updated_at: 2026-03-23 18:28
completed_at: 2026-03-23 18:28
---

## Context

The new `/aitask-qa` skill (t428_1) introduced two execution profile keys — `qa_mode` and `qa_run_tests` — documented in `profiles.md`. These keys need to be added to the settings TUI so users can edit them via `ait settings` in the Profiles tab.

## Key Files to Modify

- **`.aitask-scripts/settings/settings_app.py`**
  - `PROFILE_SCHEMA` (~line 87-108): Add `qa_mode` as enum and `qa_run_tests` as bool
  - `PROFILE_FIELD_INFO` (~line 144-275): Add short + detailed descriptions for both keys
  - `PROFILE_FIELD_GROUPS` (~line 278-291): Add a "QA Analysis" group (or append to "Post-Implementation")

## Implementation Details

### 1. Add to `PROFILE_SCHEMA`

```python
"qa_mode": ("enum", ["ask", "create_task", "implement", "plan_only"]),
"qa_run_tests": ("bool", None),
```

### 2. Add to `PROFILE_FIELD_INFO`

```python
"qa_mode": (
    "Action after QA test plan proposal",
    "Controls what happens after /aitask-qa generates a test plan.\n"
    "  ask         — Prompt with AskUserQuestion (default)\n"
    "  create_task — Auto-create a follow-up test task\n"
    "  implement   — Implement proposed tests in current session\n"
    "  plan_only   — Export test plan to file without further action\n\n"
    "Omitting this key shows the interactive prompt.",
),
"qa_run_tests": (
    "Run discovered tests during QA analysis",
    "When true (default), /aitask-qa executes discovered tests and lints.\n"
    "Set to false to skip test execution and only analyze coverage gaps.\n\n"
    "Useful when tests are slow or require special setup.",
),
```

### 3. Add to `PROFILE_FIELD_GROUPS`

Either create a new group:
```python
("QA Analysis", ["qa_mode", "qa_run_tests"]),
```
Or append to the existing "Post-Implementation" group alongside `test_followup_task`.

## Reference Files

- `.claude/skills/task-workflow/profiles.md` — Profile schema docs (already updated in t428_1)
- `.claude/skills/aitask-qa/SKILL.md` — Skill definition referencing these keys (Steps 4 and 5)
- `.aitask-scripts/settings/settings_app.py` — Existing profile schema patterns to follow

## Verification Steps

1. Run `ait settings` → navigate to Profiles tab
2. Select any profile → verify `qa_mode` and `qa_run_tests` appear
3. Toggle `qa_run_tests` → verify cycles through true/false/(unset)
4. Cycle `qa_mode` → verify all 4 options + (unset) appear
5. Press `?` on each field → verify help text expands
6. Save profile → verify YAML file contains new keys
