---
priority: medium
effort: low
depends: []
issue_type: feature
status: Done
labels: [execution_profiles, settings_tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-21 09:03
updated_at: 2026-04-21 12:24
completed_at: 2026-04-21 12:24
---

## Context

The `ait settings` TUI (`.aitask-scripts/settings/settings_app.py`) lets users edit execution-profile YAML files via a structured form. The form is driven by `PROFILE_SCHEMA` (line ~95) plus `PROFILE_FIELD_INFO` (line ~163) and `PROFILE_FIELD_GROUPS` (line ~323).

Several profile keys are actively read by skills but are missing from `PROFILE_SCHEMA`, so they can't be edited through the TUI — users must edit YAML by hand.

## Missing keys

| Key | Type | Values | Read in |
|---|---|---|---|
| `manual_verification_followup_mode` | enum | `ask`, `never` | `.claude/skills/task-workflow/manual-verification-followup.md:19` |
| `post_plan_action_for_child` | enum | same as `post_plan_action` (`start_implementation`, `ask`) | `.claude/skills/task-workflow/planning.md:290` |
| `review_default_modes` | string | comma-separated mode names | `.claude/skills/aitask-review/SKILL.md:113` |
| `review_auto_continue` | bool | — | `.claude/skills/aitask-review/SKILL.md:237` |
| `qa_tier` | string | (value domain to be confirmed from `aitask-qa/SKILL.md:37`) | `.claude/skills/aitask-qa/SKILL.md:37` |

Already set in profile YAMLs (evidence they are in use):
- `fast.yaml` — `manual_verification_followup_mode: ask`, `post_plan_action_for_child: ask`
- `remote.yaml` — `manual_verification_followup_mode: never`

## Additional inconsistency to resolve

`post_plan_action` **is** in `PROFILE_SCHEMA` but its enum is declared as `["start_implementation"]`. Per `.claude/skills/task-workflow/profiles.md:33` the documented values are `start_implementation` and `ask`. Either add `"ask"` to the enum or confirm intent (unset already means "ask" — but the enum widget won't let the user pick it).

## What to do

For each missing key, add entries in three places inside `settings_app.py`:

1. `PROFILE_SCHEMA` — `(type, options)` tuple.
2. `PROFILE_FIELD_INFO` — `(short_description, detailed_description)` tuple. Model the wording on neighbours (e.g., `manual_verification_followup_mode` mirrors `test_followup_task` tone).
3. `PROFILE_FIELD_GROUPS` — place each key under the appropriate group:
   - `manual_verification_followup_mode` → new "Manual Verification" group OR under "Post-Implementation" next to `test_followup_task`
   - `post_plan_action_for_child` → under "Planning" right after `post_plan_action`
   - `review_default_modes`, `review_auto_continue` → new "Review" group
   - `qa_tier` → under "QA Analysis" next to `qa_mode` / `qa_run_tests`

Also decide whether to add `"ask"` to the `post_plan_action` enum for consistency with docs.

## Verification

- Open `ait settings`, navigate to the profile tab, pick an existing profile, and confirm each new key is listed with a working widget.
- Edit each new key in one profile; confirm the YAML is saved correctly and round-trips on reopen.
- Confirm `manual_verification_followup_mode: never` in `remote.yaml` still renders and is editable (don't regress existing behavior).

## References

- Schema constants: `.aitask-scripts/settings/settings_app.py:95-343`
- Profile docs: `.claude/skills/task-workflow/profiles.md`
- Profile YAMLs: `aitasks/metadata/profiles/*.yaml`
