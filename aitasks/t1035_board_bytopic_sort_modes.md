---
priority: low
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [aitask_board]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1016
implemented_with: claudecode/opus4_8
created_at: 2026-06-19 13:57
updated_at: 2026-07-01 22:41
boardidx: 270
---

## Goal

Add selectable sort modes to the board's by-topic (group-by-anchor) view
(t1016_4). v1 ships a single default ordering: topic lanes are sorted
most-recently-touched first (newest `updated_at`/`created_at` among a lane's
members), with the "Ungrouped" lane always last.

## Scope

Let the user cycle/choose how topic lanes are ordered. Candidate modes:
- **Recency** (current default) — newest member first.
- **Topic id** — by root id (e.g. descending = newest topics first / ascending).
- **Size** — largest topic (most tasks) first.
- **Alphabetical** — by lane label.
- Keep "Ungrouped" pinned last in every mode.

## Implementation notes

- The ordering decision lives in the pure `group_tasks_by_topic(tasks)` in
  `.aitask-scripts/board/aitask_board.py` (recency sort + `_lane_recency` /
  `_task_recency` helpers). Thread a `sort_mode` parameter through it and the
  `refresh_board` bytopic branch.
- Add a keybinding or selector affordance to switch modes (mirror how other
  board view toggles are wired); persist the choice if appropriate (board
  settings), consistent with existing add-on toggles.
- Extend `tests/test_board_topic_group.py` with a case per sort mode; the
  recency-default test already exists.

## Context

Created as a `--followup-of 1016_4` enhancement (anchor: 1016) while
implementing the by-topic view; the user asked for richer sorting beyond the
recency default. Board reference doc (`website/content/docs/tuis/board/reference.md`)
should gain a note on the sort modes when this lands.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-07-01T19:41:45Z status=pass attempt=1 type=human
