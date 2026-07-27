---
priority: high
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: []
issue_type: enhancement
status: Implementing
labels: [aitask_board, tui, script-performance]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1243_1, t1243_2, t1243_3, t1243_4, t1243_5]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5
created_at: 2026-07-26 00:06
updated_at: 2026-07-28 01:14
---

## Problem

Reordering tasks on `ait board` is slow and noisy. Two independent causes,
confirmed by reading `.aitask-scripts/board/aitask_board.py` (8384 lines):

**1. Write amplification / transit writes.** `TaskManager.normalize_indices()`
(`aitask_board.py:1263`) renumbers *every* task in a column to the canonical
`10, 20, 30, …` sequence, calling `reload_and_save_board_fields()` per changed
task. It is invoked on:

- `_move_task_lateral()` (`:7394`) — normalizes **both** the source and target
  column after `move_task_col()` appends the task at `max_idx + 10` (`:1245`).
- `_move_task_to_extreme()` (`:7509`) — sets the moved task to
  `first - 10` / `last + 10`, then renumbers the **whole** column.
- `_move_task_vertical()` (`:7458`) — after a 2-task `swap_tasks()`; usually a
  no-op because the column is already canonical.

Consequence: moving one task from column A to column C *via* B rewrites
frontmatter for tasks in A and B that the user never intended to touch. Each
hop dirties N task files in `.aitask-data`, which is real cost as git churn and
merge-conflict surface (concurrent sessions on the `aitasks-data` branch).

**2. Whole-board render pass per keypress.** Every move path terminates in
`apply_filter()` (`:~5900`), which iterates `self.query(TaskCard)` over **every
card on the board** — not just the touched column — assigning
`card.styles.display` on each, plus building
`f"{filename} {metadata}".lower()` per card when a search filter is active.
Even the existing "fast path" for vertical moves (`_swap_adjacent_cards`,
`:7432`, which correctly does an in-place DOM `move_child` instead of a
rebuild) still calls `apply_filter()` at the end. Lateral moves additionally go
through `refresh_columns()` → `_recompose_column()` (`remove_children()` +
`_compose_widgets()` + `mount_all()`), destroying and rebuilding every card
widget of **two** columns.

**Measurements taken during exploration (this repo, ~226 task files):**

- frontmatter parse + serialize of 16 task files: **~9 ms**
- `git -C .aitask-data status --porcelain -- aitasks/`: **~4 ms**

So disk I/O and git are *not* the wall — the render pass is. The write
amplification remains a correctness/hygiene problem (git churn) even though it
is cheap in wall-clock terms.

## Goal

This is a **brainstorm / design task**. It must produce a finalized design and
a decomposition into child tasks for implementation. Four workstreams are
already identified; the design step should confirm, merge, or re-cut them.

## Workstream A — eliminate renumbering (gap indexing)

Replace the `10/20/30` canonical renumbering with **gap / midpoint indexing**
so that a single move writes **exactly one** file, and a multi-hop transit
writes nothing beyond the moved task.

Blast radius is small — verified:

- Only three sites assume the canon: `normalize_indices` `:1267`
  (`(i + 1) * 10`), `_move_task_to_extreme` `:7528/:7530` (`± 10`),
  `move_task_col` `:1252` (`max_idx + 10`).
- Every **reader** only *sorts*: `get_column_tasks()` `:957` sorts by
  `(normalize_board_idx(t.board_idx), t.filename)`. Nothing depends on values
  being contiguous, dense, or canonical.
- `lib/work_report_gather.py:210` and `lib/trail_schema.py` read `boardidx`
  for ordering/exclusion only (trail explicitly declares `boardidx`
  unrepresentable).
- The board is the **de-facto sole writer**: `aitask_update.sh --boardidx` is
  the only other write path (manual/batch); no other script writes
  `boardcol`/`boardidx`.
- **No board-movement test exists today** (`tests/test_board_*.py` covers
  views, footer visibility, topic grouping, trail, config split — not
  movement). Tests must be written as part of this work.

Design points to settle: base spacing, midpoint-insert rule, what happens when
a gap is exhausted (lazy/deferred compaction of just that column, never on the
hot path), and whether `int` remains the on-disk type (it should — the
`normalize_board_idx` coercion in `lib/task_yaml.py:54` exists precisely to
tolerate hand-edited/quoted values).

## Workstream B — render cost

- Scope `apply_filter()` to the cards actually affected instead of the whole
  board, or make it idempotent/cheap enough to be free on the unchanged cards.
- Extend the in-place DOM-move approach already used by `_swap_adjacent_cards`
  to **lateral** moves and **top/bottom** moves, so no move path recomposes a
  column.

## Workstream C — task groups inside a column

Introduce a **task group**: a named, ordered collection of tasks living inside
one column, which

- can be expanded / collapsed like a parent task's children, and
- moves **as a block** between columns and up/down within a column.

Prior art in the repo to build on / align with:

- Parent/child grouping is **filesystem-derived** (`aitasks/t130/…`) and is
  therefore not reusable for arbitrary grouping — groups must be reorderable
  and movable without moving files.
- `anchor` is an existing **frontmatter scalar** group key ("topic group key =
  root task id") with shared semantics in `.aitask-scripts/lib/topic_semantics.py`
  and a By-Topic *view* (`y`) that renders lanes
  (`_build_topic_lanes`, `aitask_board.py:~380`). This is a *view*, not an
  in-column grouping, but it is the closest data-model precedent.
- `board_config.json` is **layered** (t268_4): `columns` / `column_order` are
  *project* keys, `settings` is a *user* key, split via `lib/config_utils.py`
  (`tests/test_board_config_split.py`). Any group registry stored here must
  pick a layer deliberately.
- `expanded_tasks` (`aitask_board.py:5431`) is **in-memory only**, never
  persisted — group collapse state needs an explicit persistence decision (the
  user layer of `board_config.json` is the natural home).

Candidate data models to decide between (with trade-offs, per
`aidocs/framework/planning_conventions.md`):

1. **Frontmatter membership** — a `boardgroup:` scalar on each member, the
   direct analogue of `boardcol` / `anchor`. Survives rename/archive, zero
   coupling to config; costs one write per member on join/leave, and the
   group's own *position* in the column still needs its own ordering slot.
2. **`board_config.json` registry** — a `groups[]` block holding membership +
   order. Cheap group moves, but membership desynchronises from task files on
   rename/archive/delete and forces a layer choice.
3. Hybrid — membership in frontmatter (durable), group metadata
   (title/color/order/collapse) in config.

Note the interaction with Workstream A: moving a group as a block must **not**
degenerate into renumbering. Gap indexing should make a block move writable as
a small, bounded set of writes.

## Workstream D — bulk move commands

- A new command, available when a column is selected, that opens a **subdialog
  to select tasks** (multi-select) and moves them to a **target column**.
- A **sibling / integrated command to move tasks into and out of task groups**,
  using the same selection subdialog.

Prior art — nothing needs inventing:

- The board has **no selection state at all** today (no marking, no
  multi-select anywhere).
- The repo has a settled marking convention (t1004): `☑` / `☐` glyph, never a
  dot; marked = bold yellow; `space` toggles; `:focus:hover` uses an accent
  shade, never gray. Implemented in
  `.aitask-scripts/monitor/monitor_shared.py:558` (`_ConcernRow`) and
  `.aitask-scripts/brainstorm/widgets.py:419` /
  `brainstorm_dag_display.py:62`.
- `ColumnSelectScreen` (`ModalScreen`, already used for Collapse / Expand /
  Edit / Delete column) is a ready-made **target-column picker**.
- New commands have a natural home in the existing **command palette**
  (`KanbanCommandProvider`, which already exposes Add/Edit/Delete Column),
  which relieves pressure on the scarce single-key space (`x` = toggle
  children, `X` = collapse column are taken; `m`, `v`, `e`, `G`, `S`, `u` look
  free).

## Explicitly out of scope

**Column creation / renaming / rearranging is already implemented** and needs
no work: `board_config.json` holds user-definable `columns[]` + `column_order`,
`TaskManager.add_column()` / `update_column()` (`:1272`) manage them, `ctrl+←/→`
(`_shift_column`, `:7544`) reorders, and Add/Edit/Delete Column are exposed via
the command palette.

## Acceptance criteria

- A finalized design exists that picks one data model for task groups, with
  the rejected alternatives and their trade-offs recorded.
- The design states the ordering scheme (gap indexing parameters, compaction
  policy) and proves the "one move = one file write" property.
- Group collapse-state persistence is decided explicitly (persisted vs
  session-only, and in which config layer).
- The task is decomposed into child tasks that are each independently
  testable, with the riskiest/most uncertain piece first
  (per `aidocs/framework/planning_conventions.md` and the repo's
  testability-first decomposition convention).
- Child tasks cover: gap indexing + its regression tests (there are none
  today), render-path scoping, the group data model + persistence, block
  moves, multi-select infrastructure, the move-to-column command, and the
  group add/remove command.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-27T22:10:54Z status=pass attempt=1 type=human
