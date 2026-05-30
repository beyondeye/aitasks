---
priority: medium
effort: low
depends: [843, 851]
issue_type: documentation
status: Ready
labels: [manual_verification, web_site, task_workflow]
created_at: 2026-05-27 13:32
updated_at: 2026-05-30 00:00
boardidx: 60
---

## Context

Follow-up to t843 (`improvements_to_manual_verification_auto_mode`). t843
adds an optional auto-execution mode to the Manual Verification Procedure
with two strategies (autonomous / autonomous_with_plan) and a new
`manual_verification_mode` profile key (renamed from the original
`manual_verification_auto_mode` per the t851 brainstorm decision — see
`aiplans/archived/p851_brainstorm_better_names_for_manual_verification_auto_mode.md`).
The runtime behaviour is documented in the skill / procedure files
(`.claude/skills/task-workflow/manual-verification.md` Step 1.5,
`.claude/skills/task-workflow/auto-verification.md`,
`.claude/skills/task-workflow/profiles.md`) but the website docs need a
full pass.

**Important — coordinate with the t851 rename:** as of writing, the
rename + value-drop follow-up task from t851 has not yet been created /
executed, so the source files still use the old key
`manual_verification_auto_mode` with values
`ask | never | autonomous | prebuilt_approve | prebuilt_autorun`. The
website docs produced by this task MUST use the **new** names
(`manual_verification_mode` with values `ask | manual | autonomous |
autonomous_with_plan`). If the rename task has not landed by the time
t846 is picked up, raise it as a blocker — do not document the
soon-to-be-renamed names.

## Goal

Document the new auto-execution mode everywhere `manual_verification` is
referenced on the docs site so users can discover and understand it.

## Scope

Cover **every** page where manual-verification is referenced — not just
the primary workflow page:

1. **`website/content/docs/workflows/manual-verification.md`** — add a new
   `## Auto-execution mode` H2 covering:
   - The Step 1.5 up-front prompt and its 3 options (autonomous /
     autonomous_with_plan / skip).
   - Persistence to `aiplans/p<id>_manual_verification_auto.md`.
   - The per-item `auto` verb in the Other field of the interactive loop.
   - The `manual_verification_mode` profile knob and its four values
     (`ask`, `manual`, `autonomous`, `autonomous_with_plan`).

2. **`website/content/docs/skills/aitask-pick/`** (and any
   execution-profiles sub-page) — add `manual_verification_mode` to
   the profile schema reference alongside the existing
   `manual_verification_followup_mode`.

3. **Any other page that mentions `issue_type: manual_verification`** or
   the Pass/Fail/Skip/Defer loop — cross-link to the new mode so users
   aware of one feature discover the other. Sweep with:

   ```bash
   grep -rn "manual_verification\|Pass/Fail/Skip/Defer" website/content/
   ```

4. **Profile schema reference under the website docs** — mirror the
   schema row added in t843 to `.claude/skills/task-workflow/profiles.md`.

## Verification

- `cd website && hugo build --gc --minify` succeeds with no broken links.
- `./serve.sh` and visually confirm:
  - The new H2 renders on the manual-verification workflow page.
  - The profile schema reference table contains the new key.
  - Cross-links from other pages land on the new H2.

## Notes

- Respect CLAUDE.md "Documentation Writing" rule: describe the **current
  state only**. No "previously" / "earlier we recommended" phrasing.
- Depends on t843 being merged AND on the t851 rename follow-up landing
  (key `manual_verification_auto_mode` → `manual_verification_mode`,
  value `never` → `manual`, value `prebuilt_approve` →
  `autonomous_with_plan`, value `prebuilt_autorun` dropped). The
  follow-up rename task referenced at the end of
  `aiplans/archived/p851_brainstorm_better_names_for_manual_verification_auto_mode.md`
  must exist and be Done before picking t846 up; if missing, create it
  first.
- The task filename itself still embeds the old key name
  (`..._for_manual_verification_auto_mode.md`). Per the t851 plan's
  Migration sites §5 option (a), leave the filename and only update the
  body — `/aitask-update` updates content but not the filename.
