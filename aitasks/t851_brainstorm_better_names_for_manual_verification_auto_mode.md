---
priority: medium
effort: low
depends: [845]
issue_type: chore
status: Implementing
labels: [manual_verification, ait_settings, tui, task_workflow]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-28 11:42
updated_at: 2026-05-28 11:47
---

## Context

Follow-up from t845, which surfaced the `manual_verification_auto_mode`
profile key (added by t843) in the Settings TUI's execution-profile editor.
During review of t845, the user flagged that the **key name** and the **value
names** are not self-explanatory in the GUI, and that the explainer copy in
`profile_editor.py` is too dense — even with website docs forthcoming, the
in-TUI strings should stand on their own.

Acting on bad names now (before docs are written and external users start
referencing them in profile YAML files) is much cheaper than renaming later.

## Goal

Propose better names for:

1. The profile key itself (currently `manual_verification_auto_mode`).
2. Its five values:
   - `ask`
   - `never`
   - `autonomous`
   - `prebuilt_approve`
   - `prebuilt_autorun`
3. The short + detailed explainer strings rendered in the profile editor.

## Scope

- This is a brainstorming task — output should be a written proposal in the
  plan file with recommended new names and a rationale, NOT immediate code
  changes. A separate rename task spawns from the chosen proposal.
- All usages that need to migrate if names change:
  - `.claude/skills/task-workflow/profiles.md` — Profile Schema Reference table row
  - `.claude/skills/task-workflow/manual-verification.md` — Jinja branches
  - `.aitask-scripts/lib/profile_editor.py` — `PROFILE_SCHEMA`,
    `PROFILE_FIELD_INFO`, `PROFILE_FIELD_GROUPS` entries
  - Any profile YAML files under `aitasks/metadata/profiles/` that already
    set the key
  - Any aiplans/aitasks that mention the key by name
- Confirm there are no in-flight tasks (other than this one) that already
  reference the key/values before finalizing the rename proposal.

## Deliverables

- A short rename proposal section in this task's plan file, with:
  - Proposed new key name (1 primary + 1 alternate, with rationale)
  - Proposed new value names (e.g. `prebuilt_approve` →
    `prebuilt_with_approval`, etc.) — again, 1 primary + 1 alternate per
    value, with rationale
  - Proposed new short + detailed editor strings
- A clear decision step (or AskUserQuestion checkpoint) for the user to
  pick before any code change lands.

## Notes

- Brainstorm task, not a code-change task. Schedule the actual rename as a
  follow-up once names are agreed.
- Reference t843 (key introduction) and t845 (Settings TUI surfacing) in
  the resulting proposal so reviewers can trace the history.
