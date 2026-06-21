---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_board]
anchor: 1016
created_at: 2026-06-19 13:57
updated_at: 2026-06-19 13:57
boardidx: 80
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
