---
Task: t891_4_finalize_proposal_export.md
Parent Task: aitasks/t891_brainstorm_proposal_only_retire_plans.md
Sibling Tasks: aitasks/t891/t891_1_decision_docs_v2_architecture.md, aitasks/t891/t891_2_ops_agents_removal.md, aitasks/t891/t891_3_schema_data_tui_cleanup.md
Worktree: (decide at pick time)
Branch: aitask/t891_4_finalize_proposal_export
Base branch: main
---

# Plan — t891_4: finalize replacement (proposal export, no migration)

> **⚠️ DEFERRED — gated on the t756 chain (after t891_3). Re-verify the
> `finalize_session` anchors against as-landed code (2026-06-01 snapshot).** No
> migration / tolerate-legacy — unshipped feature.

## Code anchors (2026-06-01 snapshot — verify by name)

`.aitask-scripts/brainstorm/brainstorm_session.py`
- `finalize_session` (~L295): `plan_file = node_data.get("plan_file")` (~L310),
  `raise ValueError(... has no plan_file)` (~L312), copy `br_plans/<head>.md` →
  `aiplans/p<N>_<head>.md` (~L314-321). Remove all three.

## Decision: export strategy
Read the as-landed t756 fast-track / `module_sync` handoff first, then pick:
- **(a) Proposal export** — export the head node's **proposal** markdown to the
  aitask handoff location.
- **(b) Fast-track ownership** — if the modules fast-track already creates the
  linked aitask and owns its plan, `finalize` just marks the session
  `completed`, stops the crew runner, and links the session in task metadata (no
  file export). Prefer (b) if fast-track already covers the handoff — avoids
  duplicating it.

## Preserve
Session-completed transition, crew-runner shutdown, session↔task metadata link.

## Steps
1. Read as-landed `finalize_session` + t756 fast-track/handoff code.
2. Implement (a) or (b); strip all `plan_file`/`br_plans` references.
3. Update/remove callers or tests asserting the old plan-export behavior.

## Verification
- `finalize_session` references no `plan_file`/`br_plans`; finalizing a
  plan-less session does not raise.
- Manual end-to-end: finalize a session → aitask created/linked with the
  proposal content (not a plan).
- `grep -rn "plan_file\|br_plans" .aitask-scripts/brainstorm/` clean across the
  whole module after this child.
