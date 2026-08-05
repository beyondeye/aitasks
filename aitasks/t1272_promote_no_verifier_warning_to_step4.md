---
priority: low
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [gates, task_workflow]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
implemented_with: claudecode/opus5
created_at: 2026-07-27 23:29
updated_at: 2026-08-05 17:38
boardidx: 50176
---

## Origin

Risk-mitigation ("after") follow-up for t635_34, created at Step 8d after
implementation landed.

## Risk addressed

Goal-achievement risk (medium) from p635_34:

> **The early warning is not a documented skill contract** — it reaches every
> lane via stderr, but no skill instructs the agent to surface it, so an agent
> may not pass it on to the user.

t635_34 deliberately emitted the warning from `aitask_gate.sh
materialize-active` on **stderr only**, taking zero render/goldens blast
radius. Two reasons that was the right call at the time:

1. The obvious plan-time site — `planning.md`'s End-of-planning terminal step —
   sits entirely inside `{%- if 'risk_evaluated' in rendered_set %}`, so a
   warning there is invisible under exactly the profiles most likely to be
   misconfigured (`remote`, `rendered_gates: []`). It is the WRONG site.
2. The correct site (`SKILL.md` Step 4's Jinja-free `materialize-active` block)
   and its goldens were carrying another session's uncommitted `output_branch`
   work, so regenerating would have swept up unrelated changes.

Reason 2 is temporary. **Verify it has cleared before starting** — the
`output_branch` work landed as part of the t1265 line of commits; confirm
`git status` shows `.claude/skills/task-workflow/SKILL.md` and
`tests/golden/procs/task-workflow/SKILL-*.md` clean.

## Goal

Document the warning in the Step-4 parse contract so the agent is instructed to
surface it, rather than relying on it merely being visible in tool output.

## Scope

1. In `.claude/skills/task-workflow/SKILL.md`, Step 4 ("Materialize the
   active-gates tuple"), add a bullet to the stdout-parse list stating that a
   `Warning: ... has no verifier configured` line on **stderr** means an
   enforced gate cannot be satisfied and will block archival; the agent should
   surface it to the user and suggest `ait gates sync-registry`. Keep it
   OUTSIDE any Jinja conditional — that block is deliberately always-rendered.
2. Do NOT change the exit-code contract: the warning is advisory. A nonzero
   exit still means abort; a warning still means continue.
3. Regenerate goldens and committed prerenders in the same commit:
   `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md` plus the
   3 committed remote prerenders (`./.aitask-scripts/aitask_skill_rerender.sh
   remote` — one call per profile; only `remote` variants are git-tracked).
4. Run `./.aitask-scripts/aitask_skill_verify.sh`.

## Reference

- Emission site: `_warn_unverifiable_active` in `.aitask-scripts/aitask_gate.sh`.
- Predicate: `gate_ledger.unverifiable_reason` (shared with
  `gate_orchestrator.blocked_reason`).
- Existing warn-and-continue precedent in the same Step-4 list:
  `MATERIALIZED_UNCOMMITTED` / `NOOP_UNCOMMITTED`.

## Verification

- The rendered `SKILL.md` for all three profiles contains the new bullet
  (it must NOT be profile-conditional).
- `bash tests/test_skill_render_task_workflow.sh` passes.
- `./.aitask-scripts/aitask_skill_verify.sh` passes; goldens committed in the
  same change.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-05T14:39:07Z status=pass attempt=1 type=human
