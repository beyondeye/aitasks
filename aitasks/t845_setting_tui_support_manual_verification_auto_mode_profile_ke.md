---
priority: medium
effort: low
depends: [843]
issue_type: enhancement
status: Ready
labels: [manual_verification, ait_settings, tui, task_workflow]
created_at: 2026-05-27 13:32
updated_at: 2026-05-27 13:32
boardidx: 50
---

## Context

Follow-up to t843 (`improvements_to_manual_verification_auto_mode`). t843
adds a new execution-profile key `manual_verification_auto_mode` to the
task-workflow's Manual Verification Procedure, with values:
`ask` (default), `never`, `impromptu`, `prebuilt_approve`,
`prebuilt_autorun`. See
`.claude/skills/task-workflow/profiles.md` for the schema entry once t843
lands.

## Goal

Update the Settings TUI's execution-profile editor so users can discover
and set the new `manual_verification_auto_mode` key from the GUI, instead
of having to edit the YAML file by hand.

## Scope

- Profile editor lives in `.aitask-scripts/lib/profile_editor.py` and is
  surfaced through `ait settings` (Project Config tab → per-skill profile
  picker; plus the profile YAML editor under `.aitask-scripts/board/`).
- Add `manual_verification_auto_mode` to the editor's known-key list with
  a picker offering the five valid values:
  - `ask` (default — prompt fires)
  - `never` (skip prompt; straight to interactive)
  - `impromptu` (skip prompt; run impromptu)
  - `prebuilt_approve` (skip prompt; design + approve + execute)
  - `prebuilt_autorun` (skip prompt; design + execute, no approval)
- Mirror the UX of the existing `manual_verification_followup_mode` picker.
- Include a one-line tooltip / description per value (cribbable from the
  profiles.md schema row added in t843).

## Verification

- `ait settings` → Project Config tab → open the `default` and `fast`
  profiles → confirm the new key appears in the editor with a picker.
- Select each of the 5 values, save, re-open: value round-trips correctly.
- Open a profile that does **not** have the key set → confirm it shows as
  unset / default, not as a bogus value.

## Notes

- This is a UI-only change; no runtime behaviour change beyond making the
  key discoverable.
- Depends on t843 being merged so the key actually exists in the workflow.
