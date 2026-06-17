---
Task: t1024_auto_refresh_board_on_inflight_view.md
Worktree: (none — profile 'fast', current branch)
Branch: (current)
Base branch: main
---

# Plan: Auto-refresh the board when switching to the inflight view (t1024)

## Context

`ait board`'s **inflight view** (the gate-status view, bound to `i`) is the
primary surface for tracking gate progress on `status: Implementing` tasks,
grouped into `human` / `agent` / `blocked` columns. While the board is open,
running agents continually rewrite task files and gate ledgers on disk.

Today, switching into the inflight view (`action_view_inflight` →
`_set_base_filter("inflight")`, `aitask_board.py:4655`, `:4697`) re-renders the
columns and clears the gate cache, but does **not** re-read task files from disk
(`manager.load_tasks()`) or refresh git/lock state. Only the full `r` refresh
(`action_refresh_board`, `:4382`) and the periodic auto-refresh tick do that. So
the gate status shown on entering the view is computed from whatever was loaded
last — stale w.r.t. on-disk changes made since. For a gate-status view, that
staleness defeats the purpose.

**Goal:** entering the inflight view should reflect the latest on-disk state —
equivalent to pressing `r` as part of the switch.

**Decided behavior (confirmed with user):** only the *transition into* inflight
triggers the refresh. Re-pressing `i` (or re-clicking the In-Flight selector)
while already in the inflight view stays a no-op — `r` remains the manual
refresh gesture.

## Approach

Put the refresh at the **convergent site**, `_set_base_filter()`, not in the
`i`-key action. Two distinct user paths reach the inflight view and both funnel
through `_set_base_filter("inflight")`:
- the `i` keybinding → `action_view_inflight()` (`:4655`), and
- clicking the "In-Flight" selector segment → `BaseFilterSelector.on_click()` →
  `self.app._set_base_filter("inflight")` (`:978`).

Placing the logic in `_set_base_filter` covers both with one change (no
duplication) and automatically preserves the "no-op when already active" rule —
the method already early-returns when `name == self.base_filter` (`:4699`), so
re-press does nothing, exactly as decided.

The full-`r` refresh is: `load_tasks()` (re-read disk) + `refresh_git_status()`
+ `refresh_lock_map()` + `clear_gate_cache()` + re-render. `refresh_board()`
already does `refresh_git_status()` and `clear_gate_cache()` unconditionally, and
does `refresh_lock_map()` when called with `refresh_locks=True`. So for the
inflight transition we only need to add `load_tasks()` and pass
`refresh_locks=True`. This yields a **single** render (no double-paint / flash)
and exactly matches what `r` does.

### File: `.aitask-scripts/board/aitask_board.py` — `_set_base_filter()` (`:4697`)

Add an inflight-entry branch that re-reads disk state and requests a lock
refresh, then thread `refresh_locks` into the existing `refresh_board` call:

```python
def _set_base_filter(self, name: str):
    """Switch the base radio (a/l/f/i). No-op when already active."""
    if name == self.base_filter:
        return
    old = self.base_filter
    self.base_filter = name

    # Manage auto-expansion for the locked context-view.
    if old == "locked":
        self.expanded_tasks -= self._view_auto_expanded
        self._view_auto_expanded.clear()
    if name == "locked":
        self._auto_expand_locked()

    # The inflight view shows live gate status, so entering it should reflect
    # the latest on-disk state: re-read task files + refresh the lock map
    # (refresh_board already refreshes git status and clears the gate cache).
    # This is the same data refresh as pressing 'r'. Only the transition INTO
    # inflight refreshes — re-selecting it is a no-op via the early return above.
    refresh_locks = False
    if name == "inflight":
        self.manager.load_tasks()
        refresh_locks = True

    self._refresh_selector()
    self._update_search_placeholder()

    # Re-render board with new expansion state, then filter.
    focused = self._focused_card()
    refocus = focused.task_data.filename if focused else ""
    self.refresh_board(refocus_filename=refocus, refresh_locks=refresh_locks)
```

`action_view_inflight()` and `BaseFilterSelector.on_click()` are left unchanged.

## Tests

### File: `tests/test_board_view_filter.py` (extend)

This file already drives the real `KanbanApp` via `Pilot` against live repo
data — the right harness for testing the actual `i` keypress entry point.
Add Pilot-driven tests:

1. **`test_inflight_switch_reloads_from_disk`** — spin up the app, wrap
   `app.manager.load_tasks` with a counter (e.g. assign a wrapper that
   increments a counter and calls through, or use `unittest.mock.patch.object`
   with `wraps=`), press `i`, `pause()`, then assert: `app.base_filter ==
   "inflight"` and `load_tasks` was called ≥1 time during the switch.
2. **`test_noninflight_switch_does_not_reload`** — from the default `all` view,
   reset the `load_tasks` call counter after startup, press `l` (locked),
   `pause()`, assert `load_tasks` was **not** called by the switch — guards that
   the disk re-read is scoped to the inflight transition only.
3. **`test_inflight_repress_is_noop`** — press `i` (enter inflight), reset the
   counter, press `i` again, assert `load_tasks` was not called the second time
   (documents the confirmed re-press = no-op decision via the early return).

Use the established `KanbanApp().run_test(size=(160, 48))` + `pilot.pause()`
pattern from the existing tests in this file. Mock/`wraps` `load_tasks` so the
test asserts the *behavior* (disk re-read happens on the real keypress path),
not just an internal flag.

## Verification

- Run the board view-filter tests:
  `python3 -m pytest tests/test_board_view_filter.py -v`
  (or `bash tests/run_all_python_tests.sh`).
- Run the existing inflight test to confirm no regression:
  `python3 -m pytest tests/test_board_inflight_view.py -v`.
- Manual smoke (optional, covered by the standard Step 8 review): open
  `ait board`, switch an `Implementing` task's gate state on disk, press `i`,
  confirm the new gate state shows without a separate `r`.

## Step 9 (Post-Implementation)

Standard cleanup/merge/archival per task-workflow Step 9. Profile `fast` works on
the current branch (no worktree to remove). Commit code with
`enhancement: ... (t1024)`; this task has no plan-file-only changes beyond this
plan.

## Risk

### Code-health risk: low
- Change is ~6 lines in a single method (`_set_base_filter`) and reuses the
  existing `refresh_board(refresh_locks=...)` plumbing and `load_tasks()` — no
  new abstractions, no new call sites. · severity: low · → mitigation: TBD
- Adds synchronous disk I/O (`load_tasks`) to the `i`-key handler, but this is
  the identical operation `r` and the auto-refresh tick already perform
  synchronously, so it introduces no new performance class. · severity: low ·
  → mitigation: TBD

### Goal-achievement risk: low
- Placing the logic in `_set_base_filter` (not `action_view_inflight`) is
  deliberately chosen so the selector-click path is also covered; verified both
  paths funnel through it. The re-press no-op is preserved by the pre-existing
  early return, matching the user's confirmed decision. · severity: low ·
  → mitigation: TBD
