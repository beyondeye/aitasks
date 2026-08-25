---
priority: high
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [task-workflow, planning, gates]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-25 10:16
updated_at: 2026-08-25 10:24
---

# Durable, surface-visible "plan approved, awaiting implementation" marker

## Origin

Cross-repo exploration from thinking_app (thinking_app#320, "parallel task
workflow throughput", 2026-08-25). The downstream goal: plan several tasks in
parallel (planning is cheap on memory), defer their implementation phases, and
re-pick later skipping planning. The framework supports the mechanics but the
state is invisible.

## Problem

A task whose plan was approved and stopped ("Approve and stop here" →
`plan-approved-stop.md`) is indistinguishable from a never-touched task on
every surface:

- The stop **reverts status to `Ready`** and clears `assigned_to` — by design,
  so re-pick routes through §6.0's plan-preference and re-runs the Remote
  Drift Check.
- The `plan_approved=pass` ledger entry is explicitly an **audit record, not a
  routing signal** (`plan-approved-stop.md`; `aidocs/gates/ledger-driven-reentry.md`),
  and is only written under `record_gates: true` — of the shipped profiles only
  `fast.yaml` sets it; `default.yaml` records nothing.
- Task frontmatter has no "planned" state; statuses are
  `Ready/Editing/Implementing/Postponed/Done/Folded`.
- The board in-flight view filters `status == Implementing`, so
  approved-and-stopped tasks never appear there; on the kanban they carry the
  same `📋 Ready` badge as unplanned tasks. Ordinary cards have no
  plan-existence indicator; `ait ls` has no plan column or filter.
- On re-pick under `default`, the user gets the interactive 3-way plan prompt
  ("Use current plan / Verify plan / Create plan from scratch") with **no hint
  that an approved plan exists** or when/by what it was approved.

## Hard constraint (recorded design decision — do not violate)

`aidocs/gates/ledger-driven-reentry.md` §"Rejected alternatives" rejects
relaxing Step 3 Check 5's `Implementing` gate so a `Ready` task with recorded
`plan_approved` routes straight to IMPLEMENT — that would route around the
Step 6 Checkpoint and the Remote Drift Check on exactly the path that needs it.
**This task is about visibility and prompting, not routing.** Whatever marker
is introduced must leave the §6.0 → Checkpoint → drift-check path intact.

## Deliverable sketch (final design in planning)

- A durable per-task marker meaning "plan approved, implementation deferred",
  written by `plan-approved-stop.md` and cleared/consumed when implementation
  actually starts (and invalidated on replan/`create_new`). Candidate carriers:
  a frontmatter field, or a derived state from plan-file existence +
  `plan_verified` + recorded `plan_approved` — planning decides, but it must
  work under `default` (i.e., not depend on `record_gates: true`).
- Surfaces that consume it read-only: `ait ls` (column/filter), the pick
  prompt (§6.0's interactive question should say "an approved plan from
  <date> exists" and default accordingly), and the board (separate task,
  depends on this one).
- Semantics for staleness: what invalidates the marker (base moved? risk
  mitigation landed? — §6.0a already force-reverifies on that).

## Acceptance sketch

- Approve-and-stop a task, run `ait ls` / re-pick under `default.yaml`: the
  planned state is visible and the pick prompt names the existing approved
  plan; the Remote Drift Check still runs before any worktree fork.
- Replanning from scratch clears the marker.
