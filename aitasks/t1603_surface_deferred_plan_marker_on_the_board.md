---
priority: medium
effort: low
depends: [1595]
issue_type: enhancement
status: Implementing
labels: [ui, task-workflow]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1603_1, t1603_2, t1603_3, t1603_4, t1603_5]
folded_tasks: [1596]
assigned_to: dario-e@beyond-eye.com
anchor: 1595
created_at: 2026-08-25 12:34
updated_at: 2026-08-30 13:29
boardcol: now
boardidx: 3142
---

## Origin

Deferred from t1595, which introduced the `plan_approved_at` frontmatter marker
("plan approved, implementation deliberately deferred") and its two read
surfaces: `ait ls -v` / `--plan-approved` and the planning step's existing-plan
prompt. t1595's own deliverable sketch names the board as a **separate task
depending on it** — this is that task.

## Problem

On the board a marked task is still indistinguishable from a never-touched one:

- the kanban card renders the same `📋 Ready` badge as an unplanned task and has
  no plan-existence indicator at all;
- the in-flight view filters `status == Implementing`, so an approved-and-stopped
  task (which is `Ready` by design) never appears there;
- `TaskDetailScreen` renders per-field widgets keyed on field name, and there is
  no widget for this one — the field is invisible in the detail view even though
  it is in the file.

This is the last surface where the parallel-planning workflow ("plan several
tasks, defer their implementations, pick them up later") is still blind.

## Key files

- `.aitask-scripts/board/aitask_board.py` — the card-status composition around
  the `📋 {status}` label (two call sites: the card and the detail screen), and
  `TaskDetailScreen.compose()` for a read-only field row.
- `aidocs/framework/aitasks_extension_points.md` — layer 3 of the "Adding a new
  frontmatter field" checklist, plus the `plan_approved_at` worked example, which
  currently records "Board layer 3 ships separately". Update it when this lands.
- `.aitask-scripts/tuis/board/reference.md` (per the same checklist's layer 5) —
  add the row once the board renders the field.

## Notes / constraints

- **Read-only surface.** The marker is written and cleared exclusively by the
  task-workflow (`plan-approved-stop.md` and the four clear sites); the board
  must not offer an edit affordance for it. It is NOT a board-owned key: it is
  deliberately absent from `BOARD_KEYS` / `BOARD_LAYOUT_KEYS`, and its merge rule
  is already wired (deletion-aware `_BASE_AWARE_FIELDS` in `board/aitask_merge.py`).
- **Visibility, not routing** — the same constraint t1595 carried from
  `aidocs/gates/ledger-driven-reentry.md`. Adding a board indicator must not
  create a path that starts implementation from a `Ready` task without going
  through the planning checkpoint and its remote drift check.
- Decide explicitly whether the in-flight view should grow a second section for
  these (they are `Ready`, so they are not in-flight in the current sense) or
  whether a card indicator alone is enough. Prefer the smaller change unless the
  parallel-planning workflow clearly needs the section.
- A card is a narrow surface — budget the indicator's width rather than
  appending a full `YYYY-MM-DD HH:MM` timestamp to the status line.

## Verification

- A task carrying `plan_approved_at` renders its indicator on the board card;
  one without it renders exactly as before (assert on the render, not on a probe).
- The detail screen shows the field for a marked task and omits the row entirely
  for an unmarked one.
- Consuming the marker (start implementation) makes the indicator disappear on
  the next board refresh.

## Merged from t1596: board gate split and planned ready visibility


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

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1596** (`t1596_board_gate_split_and_planned_ready_visibility.md`)
