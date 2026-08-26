---
priority: medium
effort: medium
depends: [1595]
issue_type: enhancement
status: Folded
labels: [aitask_board, tui, gates]
gates: [risk_evaluated]
folded_into: 1603
anchor: 1595
created_at: 2026-08-25 10:16
updated_at: 2026-08-26 22:18
---

# Board: gate-reached split in the in-flight view + planned-vs-unplanned visibility for Ready tasks

## Origin

Cross-repo exploration from thinking_app (thinking_app#320, "parallel task
workflow throughput", 2026-08-25). When several tasks are planned in parallel
and implementation is deferred, the operator needs the board to answer "which
tasks already finished planning?" — today it cannot.

## Problem (evidence, aitask_board.py as of 2026-08-25)

- `_inflight_item_for()` (~line 1835) **hard-filters `status == Implementing`**
  — approved-and-stopped tasks are `Ready` and never enter the in-flight view.
- The three in-flight columns group by **required next actor**
  (`human` "Needs your action" / `agent` "Agent can continue" / `blocked`),
  not by gate reached. Gate progress exists only as free text in `next_action`
  and the per-card `gate_summary`; the two gate-derived resume states
  ("plan approved — resume implementation" vs "reviewed — post-implementation")
  land in *different* actor columns, so no phase distribution is readable from
  the layout.
- Ordinary kanban cards show `📋 Ready` identically for planned and unplanned
  tasks; the only `has_plan` use (~line 6682) toggles a modal button, not a
  card badge.
- Under `default.yaml` (no `record_gates`), in-flight cards degrade to
  "No gate information yet" with no gate summary at all.

## Deliverable sketch (final design in planning)

- Kanban cards: a plan-state badge for `Ready` tasks (consuming t1595's
  marker) so planned-awaiting-implementation reads at a glance, plus an
  `ait ls`-consistent filter if cheap.
- In-flight view: an additional grouping or visual split by **gate reached /
  workflow phase** (planned / implementing / awaiting review / post-impl),
  either as a toggle alongside the actor grouping or as per-card phase chips —
  planning decides; do not regress the actor-based ops hints
  (`[p pick] [g resume] …`).
- Decide whether approved-and-stopped (`Ready` + marker) tasks should appear
  in the in-flight view as their own group (e.g. "Planned — awaiting
  implementation") despite not being `Implementing`.
- Honest degradation when no ledger exists (default profile) — derive what is
  derivable (plan file existence, t1595 marker) instead of "No gate
  information yet".

## Dependency

Depends on t1595 (the durable marker) for the Ready-task split; the gate-split
portion of the in-flight view is implementable independently if t1595's design
shifts.
