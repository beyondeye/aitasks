---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: chore
status: Implementing
labels: [brainstorm]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-16 12:16
updated_at: 2026-06-16 13:04
---

Scrub residual references to the dropped "Detail" operation and node-level plans
from the brainstorm engine's operation help text and agent templates.

## Background

Plans were removed from brainstorm at the node level (t891 — brainstorm is now
grep-clean of the `br_plans` / `plan_file` literals; `finalize` exports the HEAD
node's *proposal* directly to `aiplans/`). There is **no longer a "Detail"
operation** — the current op registry is only: `explore`, `compare`,
`synthesize`, `finalize`, `module_decompose`/`merge`/`sync`, `freeze`.

However, the t891 cleanup removed the literal tokens but left two **prose /
help-text** references that wrongly imply a node-level plan-derivation step
(via a non-existent "Detail" op) still exists. These actively mislead readers
(they misled an exploration session into citing a "Detail → derive a plan"
stage that does not exist).

The corrected first-operation flow on a blank-initialized session is:
**Explore → Compare → Synthesize → Finalize** (no Detail / no node-plan stage).

## Stale references to fix

1. `.aitask-scripts/brainstorm/brainstorm_app.py:275` — in the `explore` op's
   `produces` help list:
   `"No plan — use Detail later to derive a plan from this proposal."`
   → Remove or rewrite. There is no `Detail` operation and brainstorm nodes no
   longer carry plans. (The op already correctly states it produces a proposal;
   just drop the dangling "use Detail later" clause.)

2. `.aitask-scripts/brainstorm/templates/explorer.md:13` — in the `## Input`
   contract: `"4. Baseline node's plan path (if one exists)"`
   → Remove this input item. Brainstorm baseline nodes no longer have plans.
   Renumber the remaining input items if needed.

## Audit (decide, lower priority)

- `.aitask-scripts/brainstorm/brainstorm_app.py` `compare` op help —
  "Does not read proposals, plans, or codebase files" / "Does NOT read
  proposals, plans, or codebase/reference files." These mention node-level
  "plans" that no longer exist. They are defensible as negations (telling the
  agent what NOT to read), so softening is optional — decide during impl whether
  to drop "plans" from the negation for accuracy.

## Do NOT touch (legitimate plan references)

- `finalize` op help + the proposal → `aiplans/` export — that is the real
  proposal-to-plan handoff and must stay.
- `module_sync` / `_resolve_linked_plan_path` (`brainstorm_crew.py` ~L815,
  ~L937) and its op help (`module_sync` reads the **linked external task's**
  `aiplans/` plan as sync context). This is an external-task plan, NOT a
  brainstorm node plan — keep it.

## Acceptance criteria

- `grep -rin 'Detail' .aitask-scripts/brainstorm/*.py
  .aitask-scripts/brainstorm/templates/*.md` shows no reference to a brainstorm
  *Detail operation* (UI "node detail" / "operation detail" screens are
  unrelated and stay).
- No brainstorm op help or agent template implies a node-level plan-derivation
  step.
- The `explore` op help and `explorer.md` Input contract read correctly with
  the plan/Detail references removed; remaining input items renumbered.
- Legitimate `finalize` → `aiplans/` and `module_sync` linked-task-plan
  references are untouched.

## Notes

- `explorer.md` is a brainstorm crew agent template (not a skill `.j2`), so no
  skill-goldens regeneration is expected — but run
  `./.aitask-scripts/aitask_skill_verify.sh` if any shared/template surface is
  touched, to be safe.
- Out of scope: website / user-facing brainstorm docs (covered separately by
  t929_3 / doc tasks). This task is the in-code op-help + template prose only.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T09:54:55Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-16T09:54:56Z status=pass attempt=1 type=machine

> **✅ gate:review_approved** run=2026-06-16T10:04:48Z status=pass attempt=1 type=human
