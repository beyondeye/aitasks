---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [verification, task-workflow, gates]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-17 11:58
updated_at: 2026-08-17 12:08
---

Brainstorm and design a staleness gate for `issue_type: manual_verification` tasks, to run as a pre-check before the Pass/Fail/Skip/Defer loop in `.claude/skills/task-workflow/manual-verification.md` (before or alongside the existing "pre-loop check — ensure the task has a checklist" step).

## Problem

`manual-verification.md`'s procedure has no staleness detection today (confirmed by reading it end to end). A manual-verification checklist is authored once (at parent-task planning time for aggregate siblings, or at Step 8c for single-task follow-ups — see `manual-verification-followup.md`) and can sit `Ready` for a long time before someone picks it. If the code/feature the checklist describes changes in the interim (a later task touches the same files, the `verifies:` origin task's behavior is amended, an upstream refactor moves the UI/API being checked), the checklist items can silently describe behavior that no longer exists — and the current procedure walks the user through verifying them as if nothing changed. The only way to catch this today is noticing during the manual step itself.

## What exists already (model from, don't duplicate)

Plan verification already has an analogous staleness mechanism worth mirroring:
- `aitask_plan_verified.sh decide <plan_file> <required> <stale_after_hours>` — returns `TOTAL:<N>` / `FRESH:<M>` / `STALE:<K>` / `LAST:<agent @ timestamp>` and a `DECISION:<SKIP|ASK_STALE|VERIFY>`.
- `plan_verification_stale_after_hours` (profile key, default 24h) and `plan_verification_required` (profile key, default 1).
- `task-workflow/planning.md`'s `ASK_STALE` branch: prompts the user with an `AskUserQuestion` when the plan verification is stale, offering to re-verify or proceed anyway.

## What this task should brainstorm/design

1. **Staleness detection.** How to determine a manual-verification checklist is stale — candidates to evaluate:
   - Commits since the task's `created_at` (or since the checklist was last seeded/edited) touching the files changed by the `verifies:` origin task(s).
   - Whether the `verifies:` origin task(s) themselves were subsequently amended/reopened/re-implemented.
   - Whether the checklist was seeded from a plan (`## Verification` H2) that has itself since drifted from the current plan file, if one still exists.
   - What "touching the same files" should mean precisely — same-file-any-line vs. same-line-range vs. semantic overlap — and how to source the origin task's changed-file list reliably (git log by task id in commit trailer/message? task's own recorded diff?).
2. **What "amend" means mechanically.** When stale, the procedure should "show current vs. what should be amended to" — design what that diff actually is: regenerated checklist items from the current plan/code state vs. the existing checklist text, presented as a proposed edit. Decide whether this is agent-authored (an agent re-derives the checklist from current source) or template-diffed (structural comparison), and how much confidence/evidence is required before proposing a change (this project's convention leans toward evidence-backed proposals, not silent guesses — see the plan-staleness precedent's `ASK_STALE` pattern of asking rather than auto-applying).
3. **Confirmation flow.** An `AskUserQuestion`-driven step, analogous to `ASK_STALE`, that shows current-vs-proposed and lets the user accept, edit, or proceed with the checklist unchanged (staleness detected but user judges it doesn't matter).
4. **Where the gate sits.** Precisely where in `manual-verification.md`'s existing procedure this new check runs relative to the "pre-loop check — ensure the task has a checklist" step (section 1) and the "auto-execution mode offer" (section 1.5) — likely a new step between/around those, gated similarly to how `plan_verification_stale_after_hours` is profile-configurable (a `manual_verification_stale_after_hours` profile key, or reuse the same one).
5. **Update mechanics.** How accepted amendments get written back to the task file — via `aitask_verification_parse.sh` (seed/convert/set) or a new subcommand — and what gets recorded (a note in the task body, a timestamp, an audit trail of "amended from X to Y") so a later re-pick doesn't re-trigger the same staleness prompt for an already-reviewed item.
6. **Scope of "stale."** Whether staleness applies per-item (only some checklist items reference changed code) or task-wide (any relevant change marks the whole checklist stale) — per-item is more precise but more complex to implement and present.

## Non-goals for this task

No implementation yet — this is the design/brainstorm pass. A follow-up implementation task (or set of child tasks) should be spawned once the design questions above are resolved, sized appropriately (likely needs splitting: detection helper script, profile plumbing, procedure/prompt wiring, and update mechanics could each be separable).

## Key files

- `.claude/skills/task-workflow/manual-verification.md` — the procedure to gate.
- `.claude/skills/task-workflow/manual-verification-followup.md` — where single-task follow-up manual-verification tasks are spawned (for context on checklist provenance).
- `.claude/skills/task-workflow/planning.md` §6.0/6.1 — the `plan_verification_stale_after_hours` / `ASK_STALE` precedent to model from.
- `.aitask-scripts/aitask_plan_verified.sh` — the analogous decision helper for plans; a new sibling script (e.g. `aitask_verification_stale.sh`) is a plausible shape for the checklist case.
- `.aitask-scripts/aitask_verification_parse.sh` — current checklist parse/seed/set primitives; likely needs a new "amend" verb.
- `.claude/skills/task-workflow/profiles.md` — where any new profile key(s) get documented.
