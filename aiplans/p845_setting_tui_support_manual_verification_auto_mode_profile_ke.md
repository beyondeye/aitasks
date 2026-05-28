---
Task: t845_setting_tui_support_manual_verification_auto_mode_profile_ke.md
Base branch: main
plan_verified: []
---

# Plan: t845 — Settings TUI support for `manual_verification_auto_mode` profile key

## Context

Task t843 added a new execution-profile key `manual_verification_auto_mode` to
the task-workflow's Manual Verification Procedure. The key controls whether the
Step 1.5 up-front auto-execution prompt fires and which auto-execution strategy
runs when it is suppressed. Today the key is only settable by hand-editing
profile YAML files. This task wires it into the Settings TUI's execution-profile
editor so users can discover and pick a value from the GUI, mirroring the
existing `manual_verification_followup_mode` field.

The change is UI-only (the runtime template in
`.claude/skills/task-workflow/manual-verification.md` already handles all 5
values); no behavior change beyond making the key discoverable.

## Note on value names (task description vs. actual implementation)

The task description in `aitasks/t845_*.md` lists the values as `ask`, `never`,
`impromptu`, `prebuilt_approve`, `prebuilt_autorun`. The actual implementation
landed in t843 uses `autonomous` instead of `impromptu` (see
`.claude/skills/task-workflow/profiles.md:40` and the Jinja branches in
`.claude/skills/task-workflow/manual-verification.md:50-102`). This plan follows
the implemented value set so the editor matches what the runtime actually
accepts.

## Critical files

- `.aitask-scripts/lib/profile_editor.py` — single-file change, three edits.

No tests reference `PROFILE_SCHEMA`, `PROFILE_FIELD_INFO`, or
`PROFILE_FIELD_GROUPS` by key. No golden files for the profile editor.

## Implementation

Three additions to `.aitask-scripts/lib/profile_editor.py`, all immediately
adjacent to the existing `manual_verification_followup_mode` entries — same
file, same pattern as the precedent:

1. **`PROFILE_SCHEMA`** (around line 60): add a new enum entry after
   `manual_verification_followup_mode`:

   ```python
   "manual_verification_auto_mode": (
       "enum",
       ["ask", "never", "autonomous", "prebuilt_approve", "prebuilt_autorun"],
   ),
   ```

2. **`PROFILE_FIELD_INFO`** (around line 178): add a description tuple
   immediately after the `manual_verification_followup_mode` entry. Short
   description fits one line; detailed description condenses the
   `profiles.md` row (5 values, one-liner per value, note about Step 1.5):

   ```python
   "manual_verification_auto_mode": (
       "Up-front auto-execution prompt mode for manual-verification tasks",
       "Controls Manual Verification Step 1.5 — whether the up-front "
       "auto-execute prompt fires, and which strategy runs when it is "
       "suppressed:\n"
       "  'ask': prompt fires (autonomous / pre-built+approve / skip)\n"
       "  'never': skip prompt; go straight to interactive\n"
       "  'autonomous': skip prompt; run autonomous strategy\n"
       "  'prebuilt_approve': skip prompt; design + approve + execute\n"
       "  'prebuilt_autorun': skip prompt; design + execute, no approval\n"
       "  (unset): same as 'ask'\n"
       "The per-item `auto` verb in the interactive loop is always "
       "available regardless of this setting."
   ),
   ```

3. **`PROFILE_FIELD_GROUPS`** (line 295): extend the existing
   `"Manual Verification"` group entry to include the new key:

   ```python
   ("Manual Verification", [
       "manual_verification_followup_mode",
       "manual_verification_auto_mode",
   ]),
   ```

The shared field renderer (`compose_profile_fields`) and value collector
(`collect_profile_values`) already handle enum keys with `_UNSET` semantics — no
changes needed there. The editor will render the new key as a `CycleField` with
options `ask | never | autonomous | prebuilt_approve | prebuilt_autorun |
(unset)`, mirroring how `manual_verification_followup_mode` renders today.

## Verification

Manual (per the task's Verification section):

1. From the repo root: `ait settings` → Profiles tab (or Project Config tab,
   depending on label) → open the `default` profile → confirm the new
   `manual_verification_auto_mode` row appears in the "Manual Verification"
   group with a 5-value cycler plus `(unset)`.
2. Repeat with the `fast` profile.
3. Cycle to each of the 5 values, save, re-open: value round-trips correctly
   (written to `aitasks/metadata/profiles/<name>.yaml`).
4. Open a profile that does not have the key set → the row shows `(unset)`
   rather than a bogus value.
5. Sanity-check the modal variant too: `ait board` → press the per-run
   profile-edit key on an agent command → confirm the new row appears
   identically (the modal uses the same `compose_profile_fields` helper).

## Step 9 (Post-Implementation)

Follow the standard task-workflow Step 9 flow: commit on the current branch
(profile `fast`, no worktree), update the plan with Final Implementation
Notes, then run `./.aitask-scripts/aitask_archive.sh 845`.
