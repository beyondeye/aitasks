---
priority: medium
effort: low
depends: [843]
issue_type: documentation
status: Ready
labels: [manual_verification, web_site, task_workflow]
created_at: 2026-05-27 13:32
updated_at: 2026-05-27 13:32
boardidx: 50
---

## Context

Follow-up to t843 (`improvements_to_manual_verification_auto_mode`). t843
adds an optional auto-execution mode to the Manual Verification Procedure
with two strategies (impromptu / pre-built) and a new
`manual_verification_auto_mode` profile key. The runtime behaviour is
documented in the skill / procedure files
(`.claude/skills/task-workflow/manual-verification.md` Step 1.5,
`.claude/skills/task-workflow/auto-verification.md`,
`.claude/skills/task-workflow/profiles.md`) but the website docs need a
full pass.

## Goal

Document the new auto-execution mode everywhere `manual_verification` is
referenced on the docs site so users can discover and understand it.

## Scope

Cover **every** page where manual-verification is referenced — not just
the primary workflow page:

1. **`website/content/docs/workflows/manual-verification.md`** — add a new
   `## Auto-execution mode` H2 covering:
   - The Step 1.5 up-front prompt and its 3 options (impromptu /
     pre-built+approve / skip).
   - Persistence to `aiplans/p<id>_manual_verification_auto.md`.
   - The per-item `auto` verb in the Other field of the interactive loop.
   - The `manual_verification_auto_mode` profile knob and its five
     values.

2. **`website/content/docs/skills/aitask-pick/`** (and any
   execution-profiles sub-page) — add `manual_verification_auto_mode` to
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
- Depends on t843 being merged.
