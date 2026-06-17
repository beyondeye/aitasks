---
priority: medium
effort: low
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_board, tui, gates]
created_at: 2026-06-17 12:10
updated_at: 2026-06-17 12:10
---

## Goal

When the user switches `ait board` into the **inflight view** (gate-status view, bound to `i`), automatically perform a full board refresh — equivalent to pressing `r` — so the gate status reflects the latest on-disk task state.

## Background

The inflight view groups `status: Implementing` tasks by gate/dependency status (`human` / `agent` / `blocked`) and is the primary surface for tracking gate progress. While the board is open, running agents continually rewrite task files and gate ledgers on disk, so a stale snapshot here is misleading precisely where freshness matters most.

## Current behavior (from exploration)

In `.aitask-scripts/board/aitask_board.py`:

- Keybinding: `Binding("i", "view_inflight", ...)` → `action_view_inflight()` (~`:4655`) → `_set_base_filter("inflight")` (~`:4697`).
- `_set_base_filter()` sets `self.base_filter` and calls `refresh_board()`, which **clears the gate cache** and re-renders the inflight columns — but it does **not** re-read task files or refresh git/lock state.
- The full refresh, `action_refresh_board()` (~`:4382`), does strictly more: `self.manager.load_tasks()` (re-reads `aitasks/*.md` + children from disk), `refresh_git_status()`, `refresh_lock_map()`, then `refresh_board(refresh_locks=True)`.

So switching to inflight re-renders gate state from already-loaded in-memory tasks (with a cleared gate cache), but won't pick up task-file/ledger changes written to disk since the board last loaded. The periodic auto-refresh timer (`_auto_refresh_tick`, ~`:4363`) eventually catches up, but the switch itself doesn't.

## Proposed change

Make switching to the inflight view trigger the same full refresh that `r` does (`load_tasks()` + git/lock refresh + re-render), so the view is immediately consistent with disk rather than waiting for the next auto-refresh tick.

Cleanest options (pick during planning):
- Have `action_view_inflight()` set the filter to `inflight` and then invoke the full-refresh path (`action_refresh_board()`), OR
- Add a guarded branch in `_set_base_filter()` for `name == "inflight"` that performs the `load_tasks()` + git/lock refresh that `action_refresh_board()` encapsulates.

Mind ordering: `base_filter` must be `inflight` before `refresh_board()` renders, and `_set_base_filter()` early-returns when already on the requested filter (so re-pressing `i` while already in inflight currently does nothing — decide whether re-pressing should still refresh).

## Acceptance criteria

- Switching to the inflight view (`i`) re-reads task files from disk and shows up-to-date gate status without a manual `r`.
- Focused-card / focus preservation continues to work across the switch.
- No regression to switching into other views (`all` / `locked` / `free`) — the full refresh is scoped to the inflight switch (unless deliberately generalized).
- Behavior of re-pressing `i` while already in inflight is decided explicitly (refresh again vs. no-op) and documented.
