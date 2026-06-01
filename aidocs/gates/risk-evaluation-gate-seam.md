---
title: Risk Evaluation → future aitask-gate-risk seam
category: idea
tags: [aitasks, gates, risk-evaluation, task-workflow, planning, forward-compat, t884, t635]
sources: [aitask-gate-framework.md]
confidence: medium
created: 2026-06-01
updated: 2026-06-01
---

# Risk Evaluation → future `aitask-gate-risk` seam

The risk-evaluation feature (t884) ships **standalone** — a profile-gated step at
the end of planning that assesses two risk dimensions and records a `## Risk`
plan section, plus a post-approval frontmatter write. It is deliberately
**not coupled** to the gate framework. This note records how it is designed to be
wrappable as a gate once the framework (t635, see [[aitask-gate-framework]]) lands,
so the integration is not lost — without putting forward-looking framework
references inside the `task-workflow/` skill sources themselves.

## Where the feature lives

- **Procedure:** `.claude/skills/task-workflow/risk-evaluation.md` — assesses
  code-health and goal-achievement risk **separately**, assigns a level to each,
  and authors the two-subsection `## Risk` plan section. Runs read-only during
  planning (`planning.md` §6.1).
- **Write:** `.claude/skills/task-workflow/SKILL.md` Step 7 — post-approval write
  of `risk_code_health` / `risk_goal_achievement` via `aitask_update.sh`.
- **Gate (profile key):** `risk_evaluation` (bool) gates the whole feature at the
  dispatch sites via Jinja; absent ⇒ feature OFF.

## How it maps to a gate

A future `aitask-gate-risk` would treat:

- the **`## Risk` plan section** as the gate's *evidence* (what was assessed), and
- the **two frontmatter levels** (`risk_code_health` / `risk_goal_achievement`)
  as the gate's *verdict*.

Conceptually the gate is *satisfied* when the `## Risk` section exists and — per
whatever policy the framework adopts — when no unmitigated `high` risk remains
(mitigations being the before/after follow-up tasks linked via
`risk_mitigation_tasks`, see t884_4).

## Why the seam already fits the gate model

The feature was built with the gate framework's two core disciplines in mind,
even though it does not depend on them:

- **Read-only evaluation, deferred mutation.** The assessment runs in read-only
  plan mode; the field writes happen at a named post-approval hook (Step 7). This
  is exactly the gate model's "compute the verdict, then record it at a defined
  point" shape.
- **Idempotent, re-runnable signal.** The `## Risk` section + the two scalar
  fields are durable on the task/plan files, so a future gate can read the prior
  verdict instead of recomputing — the local-file-is-authority property the gate
  framework relies on.

## Constraint

**Do not couple the `task-workflow/` risk-evaluation sources to the gate
framework.** This seam is documentation only until t635 provides the substrate;
the integration work itself is tracked as a follow-up against t635 (filed by
t884_7's retrospective).
