---
priority: medium
effort: medium
depends: [851]
issue_type: refactor
status: Implementing
labels: [manual_verification, task_workflow, ait_settings, skill_authoring]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-30 21:47
updated_at: 2026-05-30 21:52
---

## Context

Follow-up to the t851 brainstorm
(`aiplans/archived/p851_brainstorm_better_names_for_manual_verification_auto_mode.md`),
which produced a user-confirmed proposal to rename the
`manual_verification_auto_mode` profile key, rename two of its values,
and drop one value entirely. t851 explicitly defers the actual rename
to a separate follow-up task — this is that task.

## Goal

Apply the t851-confirmed rename + value-drop everywhere in the source
tree:

- **Key:** `manual_verification_auto_mode` → `manual_verification_mode`
- **Values:**
  - `ask` *(default)* — unchanged
  - `never` → `manual`
  - `autonomous` — unchanged
  - `prebuilt_approve` → `autonomous_with_plan`
  - `prebuilt_autorun` — **dropped entirely** (no safe use case for
    unapproved planned execution; see t851 plan §Decision for the
    rationale)

## Migration sites (verbatim from t851 plan)

1. **`aitasks/metadata/profiles/default.yaml`** (line ~4)
   - `manual_verification_auto_mode: autonomous`
     → `manual_verification_mode: autonomous`
   - Sweep all profile YAMLs under `aitasks/metadata/profiles/` for any
     other occurrence (including any user-defined profiles that may set
     `prebuilt_approve` / `prebuilt_autorun`).

2. **`.aitask-scripts/lib/profile_editor.py`**
   - `PROFILE_SCHEMA` (~line 61): rename key, drop `prebuilt_autorun`
     from the enum list, rename remaining values.
   - `PROFILE_FIELD_INFO` (~line 191): rename key, replace the short +
     detailed explainer strings with the drafts in the t851 plan §New
     editor strings.
   - `PROFILE_FIELD_GROUPS` "Manual Verification" entry (~line 315):
     rename key in the group list.

3. **`.claude/skills/task-workflow/profiles.md`** (line ~40)
   - Schema table row: rename key, drop `prebuilt_autorun`, update
     remaining value names + description column.

4. **`.claude/skills/task-workflow/manual-verification.md`** — Jinja:
   - Lines 50, 70, 102: rename `profile.manual_verification_auto_mode`
     references.
   - Line 51: `== "never"` → `== "manual"`
   - Lines 54–58: `== "autonomous"` block — value name unchanged, but
     update the displayed message text + the `manual_verification_mode:`
     literal in the prompt copy.
   - Lines 59–63: `== "prebuilt_approve"` → `== "autonomous_with_plan"`;
     update displayed message text.
   - **Lines 64–68: `== "prebuilt_autorun"` branch — DELETE entirely.**
   - Update the else-branch comment on line 69 from
     `{# manual_verification_auto_mode == "ask" or any other value #}`
     to the new key name.

5. **`aitasks/t846_documentation_for_manual_verification_auto_mode.md`**
   - Already updated (this task's prerequisite) — t846's body already
     references the new key + values per option (a) in the t851 plan
     §Migration sites. The filename still embeds the old name; leave
     it alone (per t851 plan recommendation). No action needed beyond
     confirming the body still reads correctly after this rename lands.

6. **Other in-flight references** — re-run
   `grep -rn 'manual_verification_auto_mode' aiplans/ aitasks/` before
   committing. The t851 plan confirmed only t843/t845 (archived — do
   not touch), t846 (already updated), and t851 itself (archived plan,
   do not touch) reference the old key. No surprises expected.

## Rendered / golden artifacts

`manual-verification.md` is a closure procedure used by task-workflow.
After the Jinja edits in §4 above, regenerate the affected goldens
under `tests/golden/procs/<scope>/` and `tests/golden/skills/<skill>/`
in the same commit. See CLAUDE.md "Regenerate goldens after any
`.md.j2` or closure edit" and `aidocs/skill_authoring_conventions.md`.

## Cross-agent skill ports

The Claude Code version is the source of truth. After this rename lands,
file separate follow-up aitasks (or wrap into this task's Step 8c
follow-up prompts) to update the same references in the Codex
(`.agents/skills/`) and OpenCode (`.opencode/skills/`,
`.opencode/commands/`) trees.

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` passes clean.
- `grep -rn 'manual_verification_auto_mode\|prebuilt_approve\|prebuilt_autorun' .claude/ .aitask-scripts/ aitasks/metadata/`
  returns no matches (archived plans/tasks excluded).
- Golden diffs under `tests/golden/procs/` and `tests/golden/skills/`
  contain only the expected text changes.
- Manual: `ait settings` → open the `default` profile → Manual
  Verification group → confirm the new key + values + explainer
  strings render correctly, with no orphan `prebuilt_autorun` option.

## Notes

- Once this lands, t846 becomes implementable (its body already uses
  the new names).
- CLAUDE.md "Documentation Writing" rule applies: describe the current
  state only — no "previously called…" language in any updated text.
