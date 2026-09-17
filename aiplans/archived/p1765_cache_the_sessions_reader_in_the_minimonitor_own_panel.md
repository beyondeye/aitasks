---
Task: t1765_cache_the_sessions_reader_in_the_minimonitor_own_panel.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1765 — Cache the sessions reader in the minimonitor own panel

## Context

`MiniMonitorApp._own_frozen_at` (`.aitask-scripts/monitor/minimonitor_app.py:2626`)
builds a fresh `agent_sessions.SessionsView()` on every call. It runs from
`_refresh_own_live_state` on every monitor tick while the followed agent is
frozen. Because the view is thrown away each time, its stamp cache never
helps: every tick does a full `load_safe` (read and parse the JSON), even
when the store has not changed. `SessionsView`
(`.aitask-scripts/lib/agent_sessions.py:1346`) is built so that an unchanged
store costs only a `stat`. Fix: keep one view on the app, the same way
`_marks_view` works (`monitor_shared.py:573`).

## Implementation

**Order is test first, then fix.** This gives the red/green control without
ever `git stash`ing the shared working tree, where a stash could capture
unrelated tracked edits from concurrent sessions.

1. **Write the regression test (step 2 below) first, and run it against the
   unfixed code.** Expected: `test_unchanged_store_is_read_once` FAILS with a
   `load_safe` count of 2. `test_a_rewritten_store_is_picked_up` passes, since
   it pins behavior that already works. If the "read once" test passes at this
   point, the test is wrong: stop and fix the test before touching the source.

2. **Then fix `.aitask-scripts/monitor/minimonitor_app.py`**, and rerun the
   same test file → all tests pass (green).

### Source change — `.aitask-scripts/monitor/minimonitor_app.py`
   - Add a class attribute near the other `__new__`-safe defaults (next to
     `_monitor` / `_project_root`):
     ```python
     # One cached store reader for the own panel (t1765). It lives on the class
     # (starting as None) and is created on first use, not in `__init__`: apps
     # built with `__new__` in tests never run `__init__`, and a missing
     # attribute here would be swallowed by `_own_frozen_at`'s broad `except`,
     # quietly showing "record unreadable" instead of failing.
     _own_sessions_view: "agent_sessions.SessionsView | None" = None
     ```
   - In `_own_frozen_at`, swap `agent_sessions.SessionsView().by_id(record_id)`
     for a lazily created view held on the instance:
     ```python
     view = self._own_sessions_view
     if view is None:
         view = self._own_sessions_view = agent_sessions.SessionsView()
     rec = view.by_id(record_id)
     ```
     (inside the existing `try`). Creating it lazily still resolves the store
     path (`$AITASKS_AGENT_SESSIONS_FILE`) at first read, as the old code did.
   - **No per-tick `invalidate()`.** It would force a re-read every tick and
     undo the fix. It is also not needed: the minimonitor never writes the
     store itself (restore/drop run in a detached coordinator), and every
     store write goes through `os.replace`, which creates a new inode, and
     `st_ino` is part of the stamp. Add a short comment saying so.
   - Leave the other `SessionsView()` call sites alone (`monitor_shared.py:1014`,
     `:1210`, `frozenagent_app.py:988`). They are one-off reads on a keypress
     or dispatch, not per-tick reads, so they are out of scope.

### Regression test (written and run red FIRST — step 1)

Add a class `MinimonitorOwnFrozenReaderCacheTests` to
   `tests/test_monitor_frozen_filter.py`, using the existing `_Fixture` /
   `snapshot()` helpers:
   - Build a real sessions store under `self.tmp`: `agent_sessions.load` →
     `upsert` → set the record's state to frozen with a `frozen_at` stamp →
     `dump`. Point `AITASKS_AGENT_SESSIONS_FILE` at it with `patch.dict(os.environ)`.
     Build a frozen snapshot whose `frozen_record_id` is that record's id
     (use `PaneSnapshot` directly, not the fixed `RECORD`).
   - Wrap `agent_sessions.load_safe` in a counting spy using a scoped
     `patch.object` (see the leak warning at line ~1279).
   - `test_unchanged_store_is_read_once`: call `_own_frozen_at` twice → both
     return the stamp, and the spy count is 1.
   - `test_a_rewritten_store_is_picked_up`: after the first call, rewrite the
     record's `frozen_at` and `dump` (os.replace) → the next call returns the
     new stamp. This is the control showing the cache does not go stale.
   - The pre-fix control is step 1 above: the test runs against the untouched
     source before the fix exists. No stash or any other change to the shared
     tree is involved.

## Verification

- `python3 tests/test_monitor_frozen_filter.py` (new plus existing tests pass)
- Red run (before the fix) recorded: "read once" fails with count 2; green
  run (after the fix) recorded: all pass
- `bash tests/run_all_python_tests.sh --test-dir tests` is not needed for a
  change this small; also run `python3 tests/test_minimonitor_own_mark.py` and
  `python3 tests/test_agent_sessions.py` as the nearby suites.

## Post-implementation

Step 9: current-branch mode (fast profile), so there is no merge. Archive with
`aitask_archive.sh 1765`.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** Added the class-level `_own_sessions_view = None` to `MiniMonitorApp`. `_own_frozen_at` now builds a `SessionsView` on first use and reuses it, with no per-tick invalidate. Added `MinimonitorOwnFrozenReaderCacheTests` (2 tests) to `tests/test_monitor_frozen_filter.py`, using a real sessions store pointed to by `AITASKS_AGENT_SESSIONS_FILE` and a scoped `load_safe` counting spy.
- **Deviations from plan:** None. At plan review the order was changed to test first, then fix, so no `git stash` touched the shared tree.
- **Issues encountered:** The first test draft failed in setUp because the record created by `upsert` was never `dump`ed before being reloaded. That was fixed in the fixture before taking the red reading.
- **Key decisions:** Lazy creation, not an `__init__` assignment. Apps built with `__new__` in tests never run `__init__`, and a missing attribute would be swallowed by the broad `except` as "record unreadable". Other one-off `SessionsView()` call sites (keypress/dispatch) were left unchanged.
- **Red/green:** before the fix, `test_unchanged_store_is_read_once` failed with `2 != 1`, and the rewrite control passed. After the fix, both pass, as do `test_monitor_frozen_filter.py`, `test_minimonitor_own_mark.py` and `test_agent_sessions.py`.
- **Upstream defects identified:** None
