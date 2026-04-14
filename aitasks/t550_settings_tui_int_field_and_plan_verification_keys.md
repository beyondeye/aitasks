---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [settings_tui, task_workflow]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-14 17:07
updated_at: 2026-04-14 17:12
---

## Context

Task t547_2 added two new execution profile keys:

- `plan_verification_required` (int, default `1`)
- `plan_verification_stale_after_hours` (int, default `24`)

Both are documented in `.claude/skills/task-workflow/profiles.md` and set explicitly in `aitasks/metadata/profiles/fast.yaml`. They are consumed by the plan-verify decision logic (see parent task t547 and sibling t547_3).

The `ait settings` TUI — `.aitask-scripts/settings/settings_app.py`, Textual framework — does not yet support editing these keys. Its current profile schema supports only `bool`, `enum`, and `string` field types. Adding the new keys requires introducing a new `int` field type with numeric validation, because the TUI is the primary UX for non-CLI users to customize profiles.

This task adds `int`-type support to the profile editor and registers both new keys.

## Key Files to Modify

- `.aitask-scripts/settings/settings_app.py` — the only file that needs changes.

## Reference Files for Patterns

- `.aitask-scripts/settings/settings_app.py` — three existing registries to extend:
  - `PROFILE_SCHEMA` (~line 94): dict mapping field keys to `(type, options)` tuples. Current types: `"bool"`, `"enum"`, `"string"`.
  - `PROFILE_FIELD_INFO` (~line 160): dict mapping field keys to `(short_description, long_description)` tuples used for the `?` help overlay.
  - `PROFILE_FIELD_GROUPS` (~line 309): list of `(group_label, [field_keys])` tuples for visual grouping in the editor.
- `_populate_profiles_tab()` method (~line 2641) — the method that builds the Profiles tab widgets.
- Widget rendering branch (~lines 2738–2763) — currently dispatches on `bool`/`enum`/`string`. Needs a new `int` branch.
- `.claude/skills/task-workflow/profiles.md` — the canonical schema documentation already includes both new keys; use it as the source of truth for types, defaults, and help text.
- `aitasks/metadata/profiles/fast.yaml` — reference for the actual YAML shape these keys take.

## Implementation Plan

### Step 1 — Add `int` field type

In the widget rendering branch of `_populate_profiles_tab()` (~lines 2738–2763), add a new case for `int`:

- Render a Textual `Input` widget (not `CycleField`).
- Validate on input: reject non-numeric, accept positive integers only.
- Support the existing `_UNSET` sentinel so users can clear a field back to the default.
- On save, serialize the integer as a bare YAML number (no quotes) into the profile YAML file.
- On load, accept both missing-key (show as `_UNSET`) and present-key-with-int-value cases.

Match the styling and layout of the existing `string` branch — the goal is a small, focused addition, not a refactor.

### Step 2 — Register `plan_verification_required`

Add to `PROFILE_SCHEMA`:

```python
"plan_verification_required": ("int", None),
```

Add to `PROFILE_FIELD_INFO`:

- Short: "Fresh verifications needed to skip re-verification"
- Long: "Number of fresh (non-stale) plan_verified entries that must exist in a plan file for the verify path to SKIP re-verification. Only consulted when plan_preference (or plan_preference_child) is 'verify'. Default: 1."

Add to `PROFILE_FIELD_GROUPS` in the Planning group, immediately after `plan_preference_child`.

### Step 3 — Register `plan_verification_stale_after_hours`

Add to `PROFILE_SCHEMA`:

```python
"plan_verification_stale_after_hours": ("int", None),
```

Add to `PROFILE_FIELD_INFO`:

- Short: "Hours before a verification is considered stale"
- Long: "Age (in hours) after which a plan_verified entry is considered stale and no longer counts toward the required fresh count. Default: 24."

Add to `PROFILE_FIELD_GROUPS` in the Planning group, immediately after `plan_verification_required`.

### Step 4 — Sanity check other profile editors

Confirm no other file in `.aitask-scripts/settings/` or `.aitask-scripts/board/` references profile schema — if a parallel editor exists, it will need the same treatment. Current investigation (t547_2) found `settings_app.py` is the only location.

## Verification Steps

1. `ait settings` — launch the TUI.
2. Navigate to the Profiles tab and open the `fast` profile.
3. Confirm both `plan_verification_required` and `plan_verification_stale_after_hours` appear in the Planning group with integer input widgets.
4. Enter a valid positive integer (e.g., `2`) — confirm it is accepted.
5. Enter a non-numeric value (e.g., `abc`) — confirm it is rejected with a visible error/feedback.
6. Clear the field — confirm it reverts to `_UNSET` (meaning "use default").
7. Save the profile.
8. `cat aitasks/metadata/profiles/fast.yaml` — confirm the saved value matches what was entered (or the key is absent if `_UNSET` was saved).
9. `./.aitask-scripts/aitask_scan_profiles.sh` — confirm all 3 profiles still parse cleanly.

## Notes

- Parallel-safe with sibling task t547_3 (workflow integration) — they touch different files.
- Per CLAUDE.md, `.aitask-scripts/settings/settings_app.py` is shared infrastructure across all CLI adapters (Claude Code, Codex, Gemini, OpenCode). No adapter-specific files need updating.
- Depends on t547_2 (this task) for the profile keys to exist in `profiles.md` and `fast.yaml`.
