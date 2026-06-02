---
priority: medium
effort: low
depends: [t884_5]
issue_type: documentation
status: Implementing
labels: [task_workflow, web_site]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-01 00:31
updated_at: 2026-06-02 11:44
---

## Context

Docs child of t884 (see `aiplans/p884_add_task_risk_evaluation_in_planning.md`). Per `aidocs/planning_conventions.md`, user-facing docs are a first-class child (created before the manual-verification sibling). Documents the risk-evaluation feature's user-visible surfaces. Depends on t884_1 (fields), t884_3 (planning step + `## Risk` section), t884_4 (mitigation procedure). NOT gated on t884_5 (force-reverify is invisible plumbing → a one-liner at most).

Follow `aidocs/documentation_conventions.md`: describe **current state only**, no version history; use generic placeholder project names, not real repos; say "autonomous" not "auto-execution" where relevant.

## Key Files to Modify

- `website/content/docs/` — document, on the appropriate existing pages:
  - The `risk` task field (high/medium/low) — where it shows in `ait board` and how to set it via `ait create` / `ait update`.
  - The risk-evaluation planning step (two dimensions: code-health + goal-achievement) and the `## Risk` plan section.
  - The risk-mitigation before/after follow-up flow (propose-and-confirm).
  - The `risk_evaluation` execution-profile key (opt-in; off by default) in the execution-profiles / settings docs.
  - One line on force re-verification when a "before" mitigation lands.
- Place content on the relevant per-TUI / workflow pages (e.g. board docs, execution-profiles docs, the planning/task-workflow docs). Update an `_index.md` only if the feature spans pages.

## Reference Files for Patterns

- Existing execution-profiles documentation (where keys like `qa_mode` / `manual_verification_followup_mode` are described) for the `risk_evaluation` row.
- The board docs page for documenting a task field.
- The manual-verification workflow doc (`website/content/docs/workflows/manual-verification.md`) as a model for documenting a planning-integrated procedure.

## Implementation Plan

1. Read the target pages first; extend them in place rather than creating parallel pages.
2. Add risk-field, risk-eval, mitigation, and profile-key sections.
3. Build the site to confirm no broken refs.

## Verification Steps

- `cd website && hugo build --gc --minify` succeeds with no errors/broken links.
- `cd website && ./serve.sh` and visually confirm the new sections render.

## Notes for sibling tasks

Surfaces documented here are also covered behaviorally by the t884_M manual-verification sibling.
