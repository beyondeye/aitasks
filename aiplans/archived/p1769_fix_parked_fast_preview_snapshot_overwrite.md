---
Task: t1769_fix_parked_fast_preview_snapshot_overwrite.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t1769 — Stop the fast-preview route from overwriting a parked snapshot

## Context

`monitor_core` has two capture routes, and only the bulk route
(`capture_all_classified_async` + `commit_snapshots`) checks whether a pane is
parked. The single-pane route (`capture_pane_classified_async` +
`commit_snapshot`) is what `monitor_app._fast_preview_refresh`
(`monitor_app.py:1330`) uses. That method writes `self._snapshots[pane_id] = snap`
unconditionally. So when you focus a parked card, the route:

1. captures the pane,
2. classifies it, and
3. replaces its `parked=True` snapshot with an ordinary one.

The result: the "This agent is parked" placeholder (`monitor_app.py:2020`), the
parked row rendering and the session-bar parked term all disappear for the pane
you are looking at. t1705_7 fixed the same hole for **frozen** panes at these two
functions (commit `cdadfdf68`). This task adds the parked case the same way.

**Is the parked set populated on the fast route?** Yes. The parked set is
persistent state on the monitor (`TmuxMonitor._parked_agents`), not a per-call
argument, and three places publish it:
- every full refresh, before capture (`monitor_app.py:1047`,
  `minimonitor_app.py:1611`);
- immediately after a mark toggle (`monitor_shared.py:870`).

`_fast_preview_refresh` runs between those ticks, so it reads the latest published
set. That set is at most one tick old, which is the same staleness the bulk route
already accepts. No new publish-down is needed.

**Commit-time state semantics (park racing an in-flight fast refresh).** The
parked check runs once, before the tmux await, and there is deliberately **no
second check at commit time**. The generation guard already covers the race:

- The race case is a fast capture that already passed the parked check and is
  still in flight when the agent is parked. (A capture that *starts* after the
  publish takes the new guard and commits a parked snapshot itself, so that case
  is not a race.) For the in-flight capture, the park reaches
  `App._snapshots` through the full refresh. That refresh calls `_publish_parked_agents()` synchronously
  (`monitor_app.py:1047`), then `capture_all_classified_async` reserves its
  generation `g_full` before its first await (`monitor_core.py`, first statement
  of the method).
- A fast capture that checked "not parked" before that publish reserved its own
  generation `g_fast` earlier, so `g_fast < g_full`.
- **If the fast capture commits after `g_full` is reserved,** both the app's
  `capture_generation != gen` check and `commit_snapshot`'s
  `gen != _capture_generation` check reject it, so nothing is written.
- **If it commits before,** it overwrites an *ordinary* snapshot, because the
  pane has not been rendered as parked yet, and the full refresh then writes the
  parked snapshot on top. The final state is parked either way.
- The mark-toggle publish (`monitor_shared.py:870`) writes no snapshot itself.
  For a capture already in flight, the parked snapshot arrives through the full
  refresh that the toggle schedules.
- The reverse direction (unparking) has no window: the parked guard returns
  without awaiting, so `_fast_preview_refresh` commits in the same synchronous
  run.

A commit-time re-check would duplicate this guarantee in a second place, and
`commit_snapshots` does not have one either. Instead, test T7 below pins the
invariant with a barrier-controlled interleaving, so a future change to
reservation or publish ordering fails loudly.

## Implementation

### 1. `.aitask-scripts/monitor/monitor_core.py` — `capture_pane_classified_async` (~line 3069)

Add a parked guard directly **after** the existing frozen guard. Frozen stays
first, because a pane can be both frozen and parked:

```python
gen = self._next_generation()
pane = self._pane_cache.get(pane_id)
if pane is not None and self._is_frozen_pane(pane):
    return gen, pane, "", ClassifyResult(compare_value="", frozen=True)
if pane is not None and self._is_parked_pane(pane):
    return gen, pane, "", ClassifyResult(compare_value="", parked=True)
```

Extend the docstring paragraph to cover parked panes (t1769), including why
frozen is checked first.

### 2. `monitor_core.py` — `commit_snapshot` (~line 2994)

Route `result.parked` to `_parked_snapshot`, after the generation guard and after
the frozen branch (the same order as `commit_snapshots`):

```python
if result is not None and result.frozen:
    return _frozen_snapshot(pane, time.monotonic())
if result is not None and result.parked:
    return _parked_snapshot(pane, time.monotonic())
```

Update the docstring to say it mirrors both of `commit_snapshots`' state
branches. A parked pane produced no content, so it must bypass
`_apply_bookkeeping` and leave the idle clock alone.

### 3. Tests and pre-fix controls

Every test and every control appears exactly once in this list. Parked state is
set with `mon.set_parked_agents({(session, window)})`.

Tests T1–T8 go in `tests/test_monitor_parked_capture.py` and reuse its `pane()`
and `_monitor()` helpers. They are split across two new classes that mirror
`tests/test_monitor_frozen_capture.py`: T1–T5 in `FastPreviewRouteTests`, T6–T8
in `FastPreviewAppRouteTests`. Also add a module-docstring paragraph about the
second capture route. Test T9 goes in `tests/test_monitor_frozen_capture.py`.

1. **T1: parked pane not captured.** `capture_pane_classified_async` on a
   parked pane records no capture call. It returns that same pane,
   `content == ""` and `result.parked`.
2. **T2: negative control.** An unparked pane is still captured, and so is a pane
   whose window differs from the parked pair.
3. **T3: single-pane commit.** `commit_snapshot` on T1's result returns
   `parked=True` with empty content.
4. **T4: idle clock untouched.** After T3's commit, the pane id is not in
   `mon._last_content`.
5. **T5: superseded generation.** A newer `_next_generation()` before the commit
   makes `commit_snapshot` return `None`.
6. **T6: app keeps a parked snapshot** (mounted `MonitorApp.run_test`). Seed the
   focused `%2` with a `parked=True` snapshot and park it, then await
   `_fast_preview_refresh()`. Nothing is captured, and `app._snapshots["%2"].parked`
   is still true.
7. **T7: barrier-controlled park during an in-flight fast refresh** (mounted).
   `%2` starts unparked. `fake_capture` records the call, sets an `entered`
   event, then waits on a `release` event. Steps:
   - Start `asyncio.create_task(app._fast_preview_refresh())` and wait for
     `entered`.
   - Park `%2` with `set_parked_agents`, then run the full-refresh commit:
     `capture_all_classified_async()` with a fake discovery returning `[p]`,
     then `commit_snapshots`, assigning the result to `app._snapshots`.
   - Set `release` and await the task.
   - Assert that `app._snapshots["%2"].parked` is still true and that the
     in-flight capture's content never reached `_snapshots`.

   A second case in T7 releases the fast capture *before* the full refresh (the
   other interleaving). That case asserts the snapshot is ordinary right after
   the fast commit and parked after the refresh.
8. **T8: app-level placeholder and negative control** (mounted). After T6's
   setup, `#content-preview` contains "parked" and not
   `LIVE CONTENT FROM THE CAPTURE`. The control: a live focused pane is still
   captured and gets that content, `parked=False`.
9. **T9: fast-route precedence pin.** In `FastPreviewRouteTests` in the frozen
   test file, a pane that is both frozen and parked returns `result.frozen` and
   not `result.parked`. `commit_snapshot` then yields `frozen=True, parked=False`.
10. **C1: pre-fix control for the guard.** Remove the new parked guard in
    `capture_pane_classified_async` and confirm T1, T3, T4, T6 and T8's
    placeholder assertion fail. Restore the guard.
11. **C2: pre-fix control for the commit branch.** Keep the guard but remove the
    new `result.parked` branch in `commit_snapshot`. Confirm T3, T4 and T6 fail.
    Restore the branch.
12. **C3: pre-fix control for ordering.** Swap the frozen and parked guards and
    confirm T9 fails. Restore the order.
13. **C4: pre-fix control for the generation guard.** Remove the generation
    check in both `commit_snapshot` and `_fast_preview_refresh`, and confirm T7's
    first case fails. Restore both checks.
14. **Record the counts** from C1–C4 in the plan's Final Implementation Notes.

## Verification

```bash
python3 tests/test_monitor_parked_capture.py
python3 tests/test_monitor_frozen_capture.py
python3 tests/test_monitor_focus_switch.py
python3 tests/test_monitor_finalize_offload.py
bash tests/run_all_python_tests.sh --test-dir tests   # read last line for verdict; use pipefail
```

(Run the full suite only if the box isn't in a live tmux session. The targeted
modules above cover the changed surface.)

## Step 9 (Post-Implementation)

Commit the code and tests as `bug: ... (t1769)`, then archive the task and plan
per the task-workflow Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Post-Review Changes

### Change Request 1 (2026-09-17)
- **Requested by user:** the `capture_pane_classified_async` docstring stated as
  a general rule that a parked snapshot reaches the App only through a full
  refresh. This change makes the fast route commit parked snapshots too, so the
  claim is false in general.
- **Changes made:** narrowed the explanation to the race case (a capture already
  in flight when the agent is parked) in the core docstring, in the parked test
  module docstring and `_full_refresh_commit` helper, and in this plan's
  "Commit-time state semantics" section. No behaviour change.
- **Files affected:** `.aitask-scripts/monitor/monitor_core.py`,
  `tests/test_monitor_parked_capture.py`

## Final Implementation Notes
- **Actual work done:** Added a parked guard to `capture_pane_classified_async`, placed after the frozen guard, which returns before the tmux await. Added a `result.parked` branch to `commit_snapshot`, placed after the generation guard and the frozen branch, which routes to `_parked_snapshot`. Added `FastPreviewRouteTests` (5) and `FastPreviewAppRouteTests` (5, mounted) to `tests/test_monitor_parked_capture.py`: T1–T8, with T7 as two barrier-controlled race tests covering both interleavings. Added the frozen-and-parked precedence pin (T9) to `tests/test_monitor_frozen_capture.py`.
- **Deviations from plan:** T2 tests two negative controls (an unparked pane, and a parked pair from a different window) in one test method. T8's live-pane control is its own test method. The docstring wording was narrowed after review; see Post-Review Changes.
- **Issues encountered:** None. The mounted app tests run inside `run_test` with the fake monitor swapped in, as in the frozen suite's precedent. No timer interference was observed.
- **Key decisions:** No commit-time parked re-check. The generation guard already rejects an in-flight fast capture that the park-delivering full refresh superseded, and T7 pins that. Pre-fix controls:
  - **C1**, parked guard removed: 5 failures (T1, T3, T4, T6, T8 placeholder).
  - **C2**, commit branch removed: 4 failures (T3, T4, T6, T8 placeholder).
  - **C3**, guards swapped: 1 failure (T9).
  - **C4**, generation checks removed from `commit_snapshot` and `_fast_preview_refresh`: T7's in-flight case fails, plus the superseded-generation test in both suites.
  - Code restored after each control. All non-live `test_monitor_*` / `test_minimonitor_*` modules pass. The full suite was not run, because this session is inside tmux and the live suites need an external terminal.
- **Upstream defects identified:** None
