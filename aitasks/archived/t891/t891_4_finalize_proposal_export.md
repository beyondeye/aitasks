---
priority: high
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: [t891_3]
issue_type: refactor
status: Done
labels: [ait_brainstorm, brainstom_modules, remove_support]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-01 10:52
updated_at: 2026-06-11 13:07
completed_at: 2026-06-11 13:07
---

# t891_4 — Finalize replacement: proposal export (no plan, no migration)

> **⚠️ DEFERRED — gated on the t756 chain (auto-depends on t891_3).** Do NOT
> implement until t756 lands and t891_2/t891_3 are done. **Re-verify the
> `finalize_session` anchors against the as-landed codebase** — line refs are a
> 2026-06-01 pre-modules snapshot.

## Context

Final removal child. `finalize_session()` currently requires a `plan_file`,
raises `ValueError` if missing, and copies `br_plans/<head>_plan.md` →
`aiplans/p<N>_<head>.md` as the brainstorm→aitask handoff. With the plan layer
gone (t891_2/t891_3), replace that with a **proposal export** (or rely on the
modules fast-track + aitask ownership for the handoff). `ait brainstorm` is
unshipped → no migration, no tolerate-legacy path for old `plan_file` nodes.

## Key files to modify

- `.aitask-scripts/brainstorm/brainstorm_session.py`
  - `finalize_session()` — remove the `plan_file = node_data.get("plan_file")`
    retrieval, the `raise ValueError(... has no plan_file)` guard, and the
    `br_plans/` → `aiplans/` copy. Replace with one of:
    - **(a) Proposal export:** export the head node's **proposal** markdown to the
      aitask handoff location, OR
    - **(b) Fast-track ownership:** if the modules fast-track (t756) already
      creates the linked aitask and owns its plan, `finalize` only marks the
      session `completed`, stops the crew runner, and links the session in task
      metadata — no file export.
  - Decide (a) vs (b) by reading how the as-landed t756 fast-track / `module_sync`
    handoff works; prefer not duplicating what fast-track already does.

## Must preserve

- The session-completed status transition, crew-runner shutdown, and
  session↔task metadata linking that `finalize_session` already does.

## Implementation plan

1. Read the as-landed `finalize_session` and the t756 fast-track/handoff code.
2. Choose export strategy (a) or (b) and implement; remove all `plan_file` /
   `br_plans` references from the function.
3. Update / remove any callers or tests asserting the old plan-export behavior.

## Verification

- `finalize_session` no longer references `plan_file` or `br_plans`; finalizing a
  session with no plan does not raise.
- The brainstorm→aitask handoff still works end-to-end (manual: finalize a
  session, confirm the aitask is created/linked with the proposal content, not a
  plan).
- brainstorm tests (if any) pass; `grep -rn "plan_file\|br_plans" .aitask-scripts/brainstorm/`
  is clean across the whole module after this child.
