---
Task: t851_brainstorm_better_names_for_manual_verification_auto_mode.md
Base branch: main
plan_verified: []
---

# t851 — Rename proposal: `manual_verification_auto_mode` → `manual_verification_mode`

## Context

`manual_verification_auto_mode` was introduced by t843 to control the
Manual Verification "Step 1.5" up-front prompt (the offer to auto-execute
the whole verification checklist before the interactive
Pass/Fail/Skip/Defer loop). t845 then surfaced the key in the Settings
TUI's profile editor.

During the t845 review the user flagged that:

1. The key name is generic — "auto mode" doesn't say which verification
   it gates.
2. The value names mix orthogonal axes — `autonomous` vs
   `prebuilt_approve` / `prebuilt_autorun` is hard to read at a glance.
3. The `prebuilt_autorun` value (design + run without approval) was
   added for symmetry but has no clear safe use case — letting the agent
   execute an unreviewed auto-verification plan without a human gate
   risks running destructive/expensive commands that the prebuilt-plan
   design step was meant to surface for approval in the first place.

t846 (pending) will write user-facing docs. Renaming now — before docs
land and before external users start referencing these names in their
profile YAMLs — is much cheaper than renaming later.

This task is brainstorming. The decision has been locked in below. A
separate follow-up task will execute the rename + value drop.

## Decision (user-confirmed)

### Key

`manual_verification_auto_mode` → **`manual_verification_mode`**

- Drops the redundant `auto_` infix — the key clearly gates Manual
  Verification behavior, and "mode" is sufficient.
- Preserves the `manual_verification_` prefix for symmetry with the
  sibling key `manual_verification_followup_mode`.

### Values

| Current             | **New**                | Notes                                                         |
|---------------------|------------------------|---------------------------------------------------------------|
| `ask` *(default)*   | `ask` *(default)*      | Unchanged. Default behavior.                                  |
| `never`             | `manual`               | Reads naturally: "manual mode = no auto, do it yourself".    |
| `autonomous`        | `autonomous`           | Unchanged — already clear.                                    |
| `prebuilt_approve`  | `autonomous_with_plan` | The agent designs the plan up front and waits for approval.   |
| `prebuilt_autorun`  | **(dropped)**          | No safe use case for unapproved planned execution.            |

YAML feel:

```yaml
manual_verification_mode: ask                   # default — show the prompt
manual_verification_mode: manual                # skip auto entirely
manual_verification_mode: autonomous            # on-the-fly auto-verify
manual_verification_mode: autonomous_with_plan  # design + approve + execute
```

### New editor strings (for `PROFILE_FIELD_INFO`)

**Short description:**

> "Manual verification mode: how (or whether) to auto-run the checklist"

**Detailed description:**

```
Controls Manual Verification Step 1.5 — the up-front offer to auto-run
the verification checklist before the interactive Pass/Fail/Skip/Defer
loop. The per-item `auto` action inside the interactive loop is always
available, regardless of this setting.

  ask                  — show the offer prompt (default)
  manual               — skip the offer; go straight to interactive
  autonomous           — auto-verify each item as the agent reaches it
                         (no upfront plan-design step)
  autonomous_with_plan — design the per-item plan up front, then enter
                         plan mode for your approval before running

  (unset) — same as `ask`
```

## Migration sites (for the follow-up rename task)

All occurrences confirmed by grep (non-archived only):

1. **`aitasks/metadata/profiles/default.yaml`** (line 4)
   - `manual_verification_auto_mode: autonomous`
     → `manual_verification_mode: autonomous`

2. **`.aitask-scripts/lib/profile_editor.py`**
   - `PROFILE_SCHEMA` entry (~line 61): rename key, **drop
     `prebuilt_autorun`** from the enum list, rename remaining values.
   - `PROFILE_FIELD_INFO` entry (~line 191): rename key, replace short
     + detailed strings with the drafts above.
   - `PROFILE_FIELD_GROUPS` "Manual Verification" entry (~line 315):
     rename key in the group list.

3. **`.claude/skills/task-workflow/profiles.md`** (line 40)
   - Schema table row: rename key, drop `prebuilt_autorun`, update
     remaining value names in the description column.

4. **`.claude/skills/task-workflow/manual-verification.md`** — Jinja:
   - Lines 50, 70, 102: rename `profile.manual_verification_auto_mode`
     references.
   - Line 51: `== "never"` → `== "manual"`
   - Lines 54–58: `== "autonomous"` block — value name unchanged, but
     update the displayed message text and the `manual_verification_mode:`
     literal in the prompt copy.
   - Lines 59–63: `== "prebuilt_approve"` → `== "autonomous_with_plan"`;
     update displayed message text.
   - **Lines 64–68: `== "prebuilt_autorun"` branch — DELETE entirely.**
   - Update the else-branch comment on line 69 from
     `{# manual_verification_auto_mode == "ask" or any other value #}`
     to the new key name.

5. **`aitasks/t846_documentation_for_manual_verification_auto_mode.md`**
   - Lines 15, 18, 41, 45 — task body references the old key. The
     **task filename also embeds the old name**. Two options:
     a) Update t846's description in place (rename references in body)
        and leave the filename — `/aitask-update` updates content but
        not the filename.
     b) Archive t846 and recreate it under the new name. Heavier;
        only worth it if t846 hasn't been started.
     The follow-up rename task should pick (a) unless the user prefers
     otherwise. Once t846 lands, its produced website docs must also
     use the new key/value names.

6. **Goldens regeneration** (per `CLAUDE.md` Skills section)
   - `manual-verification.md` is a closure procedure used by
     task-workflow. After the Jinja edits in #4 above, regenerate the
     affected goldens under `tests/golden/procs/<scope>/` and
     `tests/golden/skills/<skill>/` in the **same commit**.
   - Run `./.aitask-scripts/aitask_skill_verify.sh` before committing
     to confirm the stub-surface and dep-closure render cleanly.

7. **Cross-agent skill ports** (per `CLAUDE.md` "Working on Skills"):
   - The Claude Code version is the source of truth. After the rename
     lands here, file separate follow-up aitasks to update the same
     references in the Codex (`.agents/skills/`) and OpenCode
     (`.opencode/skills/`, `.opencode/commands/`) trees.

8. **Other in-flight references** — `grep -rn 'manual_verification_auto_mode'
   aiplans/ aitasks/` confirms only t843/t845 (archived — do not touch),
   t846 (pending — handled above), and t851 (this task) reference the
   key. No surprises.

## Follow-up

After this brainstorm is committed and archived, create a single
follow-up task with the migration checklist above. Recommended title:

> "Rename `manual_verification_auto_mode` → `manual_verification_mode`
> and drop `prebuilt_autorun` value (t851)"

Issue type: `refactor`. Effort: `medium` (touches 4 files + goldens +
t846 update). Depends on: t851.

## Verification

For this brainstorm:
- User has confirmed the new names (this section already records the
  decision — no further verification needed).

For the follow-up rename task (out of scope here, listed for completeness):
- `./.aitask-scripts/aitask_skill_verify.sh` — clean
- Diff `tests/golden/procs/**` and `tests/golden/skills/**` — only the
  expected per-rename text changes
- Manual: `ait settings` → open default profile → Manual Verification
  group → confirm the new key + values + explainer strings render
  correctly with no orphan `prebuilt_autorun` option

## Step 9 (Post-Implementation)

This is a brainstorm — no code changes. The Step 8 "code commit" is a
no-op; only this plan file is committed (via `./ait git`). Step 8b
(upstream defect follow-up) and Step 8c (manual-verification follow-up)
are not applicable. Step 9 archives this task as normal.

The follow-up rename task is created **after** archival — either
through `/aitask-create` invoked by the user, or by an explicit
final-step prompt at the end of this workflow's Step 8.

## Final Implementation Notes

- **Actual work done:** Drafted the rename proposal, presented the
  initial brainstorm via plan mode, and recorded the user-confirmed
  decision in this plan file. The user finalized the names during
  Phase 4 plan-mode review (not via a later iteration): key
  `manual_verification_mode`, values `ask` (default) / `manual` /
  `autonomous` / `autonomous_with_plan`, and `prebuilt_autorun`
  dropped entirely.
- **Deviations from plan:** None. The initial brainstorm offered two
  proposal shapes (rename key + values vs rename values only); the
  user chose the rename-key-and-values shape with their own value
  names, which replaced the drafted variants. Plan file rewritten to
  reflect the locked decision before ExitPlanMode.
- **Issues encountered:** None.
- **Key decisions:**
  - Dropped `prebuilt_autorun` (planned-execution without approval) —
    no clear safe use case; user-driven decision. Removing the value
    requires deleting the corresponding Jinja branch in
    `.claude/skills/task-workflow/manual-verification.md` lines 64–68
    during the follow-up rename task.
  - Kept the `manual_verification_` prefix on the key (for symmetry
    with `manual_verification_followup_mode`) but dropped the
    redundant `auto_` infix.
- **Upstream defects identified:** None.
