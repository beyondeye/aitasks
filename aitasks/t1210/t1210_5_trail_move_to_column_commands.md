---
priority: medium
effort: low
depends: [t1210_4, t1243_3, t1243_7]
issue_type: feature
status: Ready
labels: [aitask_board, tui]
gates: [risk_evaluated]
anchor: 1210
created_at: 2026-07-22 16:17
updated_at: 2026-07-28 01:18
---

## Context

**T5** of the Implementation Trails decomposition (RFC §14 in
`aidocs/implementation_trail_design.md`; parent t1210). The move-to-column
commands in the By-Trail view — the **passive t1162 report bridge** (a v1 user
decision): the user moves tasks/waves into a board column; the Work Report
reads that column unchanged. RFC §9.4 and §10 are the spec.

## Key files to modify

- `.aitask-scripts/board/aitask_board.py` — `m` (move focused entry's task)
  and `M` (move focused wave's tasks in position order) actions in the
  By-Trail view, with a column-picker modal; `check_action` gating so they
  appear only in By-Trail with a movable (non-ghost) focus.

## Reference files for patterns

- Column-move machinery (verified): `TaskManager.move_task_col` at
  `aitask_board.py:954-962` (appends bottom: `board_idx = max+10`),
  `normalize_indices` at `:972-979`, writes via
  `Task.reload_and_save_board_fields` at `:252-267` (direct file edit — NOT
  `aitask_update.sh`; this is the board's sanctioned write path for
  boardcol/boardidx).
- `aidocs/implementation_trail_design.md` §9.4: wave moves preserve entry
  `position` order; ghost cards (archived / missing / cross-repo members)
  are excluded from both commands; the trail artifact is never consulted or
  modified by the move.
- t1162 contract (§10): the bridge adds NO code coupling — do not touch the
  work-report gatherer or skill.

## Implementation plan

1. Column-picker modal listing configured columns (from `column_order`) plus
   the dynamic unordered column.
2. `m`: `move_task_col(task, col)` + `normalize_indices(col)`.
3. `M`: iterate the wave's movable entries in `position` order calling
   `move_task_col`, then normalize once — order in the target column matches
   wave order.
4. Refresh the underlying task set so a subsequent view switch shows the
   moves; the By-Trail view itself re-renders badges (boardcol is displayed,
   never digested — a move must NOT flip the trail to stale, per RFC §8.1).

## Verification

- Unit tests over the manager mutators: wave move into an empty column yields
  position order; ghost entries skipped with a which-item report.
- Pilot test: `M` then switch to normal view → tasks present in the target
  column in order.
- Negative control: after a move, the trail drift check still reports
  CURRENT (boardidx/boardcol excluded from the digest).

## Coordination

`t1268` (By-Trail refresh semantics and key/footer contract) edits the same
`KanbanApp.BINDINGS` list and the same `check_action` `bytrail` branches this
task adds `m` / `M` to, and reworks the By-Trail footer labels and the
per-card hint line at `TrailTaskCard.compose`. Whichever lands second must
rebase onto the other's gating and label changes. Neither blocks the other,
but do not develop them in parallel on that region without checking.

Note also that step 4 of the implementation plan above ("refresh the
underlying task set so a subsequent view switch shows the moves") overlaps
t1268's local recompute path — reuse whatever t1268 lands rather than adding a
second reload route.

## Notes for sibling tasks

**t1243 replaces the move machinery this task's plan is written against.** The
`## Implementation plan` above calls `TaskManager.move_task_col` +
`normalize_indices`; both are removed by **t1243_3** (`gap_indexing`), which is
why this task now depends on it. Re-verify the plan against the landed API
before implementing:

- `normalize_indices` is renamed `respace_column` and becomes an
  **exhaustion-only** remedy — do **not** call it after a move. Renumbering a
  whole column on every move is the write-amplification t1243 exists to remove.
- Use the gap-indexed manager API instead: `move_task_to_column(task, col)` for
  a single task (**1 file write**), and **`move_tasks_to_column(tasks, col)`**
  for the wave move — it assigns K contiguous indices in input order, so `M`
  gets "target column order matches wave order" for free with **exactly K
  writes**, replacing the plan's "iterate `move_task_col`, then normalize once".
- Ordering primitives live in `.aitask-scripts/lib/board_ordering.py`.

**Do not build a second column picker.** **t1243_7**
(`move_to_column_command`) ships the shared chain — a `SelectionList`
task-select subdialog plus `ColumnSelectScreen` for the destination, with the
synthetic `unordered` entry injected — bound to `m`. Reuse it so `m` means the
same thing in every view ("move the selected task(s) to a column"), with
per-view semantics gated in `check_action`. This task's `M` (wave move) remains
By-Trail-specific.

Ghost-entry exclusion and the "trail artifact is never consulted or modified by
the move" contract are unchanged by t1243.
