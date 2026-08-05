---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [framework, task_workflow, risk_evaluation, planning]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/fable5
created_at: 2026-08-05 08:37
updated_at: 2026-08-05 09:09
---

## Context

The task-workflow risk machinery (`risk-evaluation.md` + `risk-mitigation-followup.md`)
currently offers exactly one disposition for a confirmed mitigation: spawn it as a
separate task — `timing: before` (Step 7 creates it, wires `depends:` +
`risk_mitigation_tasks`, and **ends the session**, reverting the original to
Ready/Blocked) or `timing: after` (Step 8d spawns a non-blocking follow-up).

This mechanism works and **stays** — it is the right shape for heavyweight or
plan-invalidating mitigations. But it has real costs the user has hit in practice:

- A stopped "before"-blocked task is easy to forget (nothing surfaces that it is
  waiting beyond the board's Blocked state).
- When the original is one sibling of a multi-child family, prioritizing the
  spawned mitigation against the other children is awkward.
- The workflow now runs multiple AI review rounds (shadow-agent `plan-challenge`
  at planning, `impl-challenge` at implementation review), which raises confidence
  in larger single-task executions — and 1M-context agents support them. Average
  per-task execution time is up, so folding small mitigations into the main task
  is often cheaper than paying another full task lifecycle.
- Shadow-agent reviews only see the **plan**: an inline pre/post phase gets
  multi-round review coverage automatically, while a spawned mitigation task is
  invisible to it. This is a genuine quality argument for inlining, worth citing
  in the user-facing guidance.

## Goal

Give the user a per-mitigation choice, at Part-1 (design-in-planning) time, to
**incorporate a mitigation into the main task's implementation plan as a pre- or
post-phase** instead of spawning a separate task — with decision-support metrics
so it is clear when inlining is safe. The separate-task path remains fully
available and remains the default recommendation whenever inlining is not
clearly safe.

## Design sketch (from exploration)

1. **Extend the `### Planned mitigations` line contract** in
   `risk-mitigation-followup.md` from `timing: before | after` to
   `timing: before | after | pre-phase | post-phase`. The lines are parsed by
   the agent (Parts 2/3), not by shell scripts, and `aitask_gate_risk.sh` only
   validates the `## Risk` section shape + frontmatter levels — so the contract
   extension costs no script/verifier changes.

2. **Add two per-mitigation decision metrics** to the line format and the Part-1
   proposal display, both agent-estimated at design time (like `priority`/`effort`
   already on the line):
   - `inline_risk: low|medium|high` — risk of incorporating this mitigation into
     the main task. Estimate from separability: an independently-verifiable,
     bounded addition (e.g. a characterization test) is low; work that could
     invalidate or reshape the plan (e.g. an approach spike) is high.
   - `added_complexity: low|medium|high` — how much the mitigation grows the
     task, estimated **relative to the plan's own scope** (a medium-effort
     mitigation attached to a large plan may still be `low` added complexity;
     the same mitigation on a tiny plan is `high`).

3. **Part 1 prompt changes:** present each candidate with its timing, metrics,
   and a per-mitigation recommendation derived from them (both metrics low →
   suggest inline as pre/post phase; any metric high → suggest spawning;
   medium → judgement, lean spawn). The user always decides — extend the
   existing propose-and-confirm AskUserQuestion flow so the disposition
   (spawn-before / spawn-after / inline-pre-phase / inline-post-phase / drop)
   is chosen per mitigation. Keep the existing "No mitigations" / "Create all
   proposed" fast paths sensible.

4. **Inline mitigations become numbered plan steps:** pre-phase entries are
   prepended to (and post-phase appended to) the plan's implementation steps as
   explicit phases, cross-referenced from the `## Risk` bullet's `→ mitigation:`
   link (e.g. `→ mitigation: inline pre-phase step 1`). Add a line to
   `.aitask-scripts/skill_templates/_planning_plan_contract.md` noting that
   confirmed inline risk mitigations appear as explicit pre/post-phase steps.
   The `RISK_OK` guard (planning.md) is untouched — `## Risk` still exists.

5. **Spawn paths filter on timing:** Part 2 (Step 7) keeps reading only
   `timing: before` lines; Part 3 (Step 8d) only `timing: after` lines — inline
   entries are naturally skipped, so no dispatch-condition changes beyond
   documenting the new timings. `risk_mitigation_tasks` frontmatter and the
   §6.0a force-reverify machinery apply only to spawned mitigations (inline ones
   land with the task itself; nothing to track).

## Key files (all in this repo; edit canonical sources, never renders)

- `.claude/skills/task-workflow/risk-mitigation-followup.md` — Parts 1–3: line
  contract, metrics, prompt flow, timing filters.
- `.claude/skills/task-workflow/risk-evaluation.md` — only if the `## Risk`
  bullet format needs the inline cross-reference form documented.
- `.claude/skills/task-workflow/planning.md` — §6.1 end-of-planning text
  describing the mitigation design step ("proposes before/after mitigation
  tasks" → include inline phases).
- `.aitask-scripts/skill_templates/_planning_plan_contract.md` — 1-line
  addition for inline pre/post phases.
- Goldens under `tests/golden/procs/task-workflow/` — regenerate **in the same
  commit** (see `aidocs/framework/skill_authoring_conventions.md`, golden loop).
- `website/content/docs/workflows/risk-evaluation.md` — document the inline
  option, the two metrics, and when inlining is recommended (cite the
  shadow-review-coverage argument).

## Coordination

- **t1331** (`guard_risk_mitigation_reentry`, open, kept separate by decision at
  exploration time): fixes Part 2 idempotency + §6.0a inertness under
  `plan_preference: use_current`. This task rewrites the same Parts — land
  compatibly: do not change the `created: t<id>` annotation semantics t1331's
  guard will key on, and rebase whichever lands second.

## Verification

- Render check: `./.aitask-scripts/aitask_skill_rerender.sh` for affected
  profiles; goldens regenerated in the same commit
  (`tests/test_skill_render_task_workflow.sh` passes).
- Walk a fixture plan through Part 1 with mixed dispositions (one spawned
  `before`, one inline `pre-phase`, one inline `post-phase`): confirm Step 7
  creates only the spawned one, Step 8d creates nothing, inline entries appear
  as plan phases, and `aitask_gate_risk.sh` still passes the plan.
- Confirm a plan with only inline mitigations does NOT trigger the Step 7
  session-stop branch (`risk_before_created` stays false).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T06:09:43Z status=pass attempt=1 type=human
