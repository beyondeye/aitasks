---
Task: t2210_fix_shadow_zone_mounted_refresh_race.md
Base branch: main
Output branch: main
---

# t2210 — Fix the mounted shadow-zone test race

## Context

`tests/test_monitor_shadow_zone.py::MountedShadowColumnTests` flakes, at about
2–6 failing runs in 30. The task blames the mount-time `first_refresh` worker
holding `_refresh_inflight`. **Under a plain run, that is not the mechanism:**
the module pops `TMUX`/`TMUX_PANE` at import (lines 42–43). `on_mount` therefore
takes the not-inside-tmux early return, and neither `_start_monitoring()` nor
`first_refresh` ever runs.

Reproduced on this host (1 failure in 20 pytest runs of the class). The
failure: `test_full_refresh_renders_the_shadow_column_from_the_pane_list`
reported `'%1' != '%2'` at `assertEqual(app._focused_pane_id, "%2")`.

**The real mechanism is deferred UI work that a single `pilot.pause()` does not
reliably drain.** `pilot.pause()` is `wait_for_idle(0)`, which depends on CPU
idleness, so the drain gets less reliable under load. One `_refresh_data()`
queues the following, none of it awaited:
- `call_after_refresh(_restore_focus, saved_pane_id, …)` (`monitor_app.py:1209`);
- `_schedule_shadow_fit_check()` → `call_after_refresh(_apply_shadow_visibility, …)`
  (`monitor_app.py:3099-3107`). This is the `col.display` False failure;
- `run_worker(_apply_preview_render / _apply_shadow_render)` (groups `preview` /
  `shadow-preview`, `monitor_app.py:2181`, `:2332`). This is the
  preview-text assertions;
- `Widget.focus()` itself is `app.call_later(set_focus)`, and
  `on_descendant_focus` sets `_focused_pane_id` only after the focus event
  bubbles. When the test's second refresh runs before that lands, it captures
  `saved_pane_id='%1'` and `_restore_focus` re-pins `%1`. That is the observed
  failure.

Textual 8.2.7 ordering facts the fix relies on (verified in the source):
`call_later` and `call_after_refresh` both post to the App's FIFO message queue.
`InvokeLater` callbacks are appended to the screen's FIFO `_callbacks` list and
run after the next repaint. So a sentinel posted via `call_after_refresh` runs
only after every earlier-queued after-refresh callback.

A second, unproven exposure, possibly the one behind the xdist-lane failure the
task records: if `TMUX` is present at mount time, `_start_monitoring()`
**replaces the stubbed `app._monitor` with a real `TmuxMonitor`**, and
`first_refresh` + the interval timer then run against it. Some suite modules
write `TMUX` (`test_minimonitor_startup_input_latency.py:595`, restored;
`test_shadow_q_harness.py:404`, restored by its `tearDown`). Nothing proves a
leak, so the plan guards and asserts this precondition rather than claiming it
as the cause.

Intended outcome: the module's mounted tests wait on **ordering**, not on time.
All existing assertions stay unchanged. One new test (step 6) makes the
existing "refresh renders the column" claim actually discriminating.

## Implementation (single file: `tests/test_monitor_shadow_zone.py`)

1. **Add two module-level helpers** next to `_run_mounted`:

   ```python
   _SETTLE_TIMEOUT = 10.0
   _RENDER_GROUPS = frozenset({"preview", "shadow-preview"})

   async def _until(pilot, predicate, what, *, timeout=_SETTLE_TIMEOUT):
       """Pump the app until `predicate()` holds; fail loudly at the deadline."""
       loop = asyncio.get_running_loop()
       deadline = loop.time() + timeout
       while not predicate():
           if loop.time() > deadline:
               raise AssertionError(f"timed out after {timeout}s waiting for {what}")
           await pilot.pause()

   _TERMINAL = frozenset({WorkerState.SUCCESS, WorkerState.CANCELLED,
                          WorkerState.ERROR})

   def _worker_done(w) -> bool:
       """Terminal state, OR a cancellation that landed before `_run` began.

       Textual 8.2.7: `Worker._start` sets RUNNING and only then schedules
       `_run`. `cancel()` arriving first cancels the task before `_run`'s
       CancelledError handler exists, so the task finishes cancelled while
       `state` stays RUNNING forever. Only the task tells the truth then.
       """
       if w.state in _TERMINAL:
           return True
       task = getattr(w, "_task", None)
       if task is None:
           return False  # PENDING: not started yet
       if not task.done():
           return False
       if task.cancelled() or w.is_cancelled:
           return True  # superseded before it ran
       raise AssertionError(  # done, not cancelled, still RUNNING: unknown shape
           f"worker {w.name!r} finished in state {w.state} — Textual internals changed?")

   async def _settle(app, pilot, *, rounds=3, timeout=_SETTLE_TIMEOUT):
       """Drain what a refresh / focus() deferred — by ordering, not by time.

       Each round waits until every render-group worker the app has EVER
       started (the `_make_app` run_worker spy log, so replacements and
       workers that already left `app.workers` are included) is in a
       terminal state, then posts a sentinel through call_after_refresh and
       pumps until it fires: earlier call_later messages and after-refresh
       callbacks (FIFO in Textual) have run by then. Several rounds cover one
       deferred step queueing the next (refresh -> _restore_focus -> render
       worker -> scroll callback). One deadline bounds the whole call.
       """
       loop = asyncio.get_running_loop()
       deadline = loop.time() + timeout
       log = app._test_render_workers
       for _ in range(rounds):
           await _until(pilot, lambda: all(_worker_done(w) for w in log),
                        "preview render workers to finish",
                        timeout=max(0.0, deadline - loop.time()))
           failed = [w for w in log if w.state is WorkerState.ERROR]
           if failed:
               raise AssertionError(
                   f"preview render worker failed: {failed[0].error!r}")
           fired: list[bool] = []
           app.call_after_refresh(fired.append, True)
           await _until(pilot, lambda: bool(fired), "deferred callbacks to run",
                        timeout=max(0.0, deadline - loop.time()))
   ```

   **Superseded workers are normal, not failures.** `preview` and
   `shadow-preview` are started `exclusive=True`, so a deferred
   `_restore_focus` or a focus change can cancel a render that is in flight.
   For that, `Worker.wait()` / `wait_for_complete(list)` raise
   `WorkerCancelled`, and `WorkerError` for a still-`PENDING` worker. A
   finished worker is also dropped from `app.workers`, so a snapshot can never
   see it. The helper therefore **never calls `wait()`**. It polls
   `_worker_done` over the spy log, treating `CANCELLED` as
   superseded-and-done. So is the **cancelled-before-start** shape: task done
   and cancelled, `state` still `RUNNING`. Textual 8.2.7 can produce it for
   two back-to-back exclusive renders. That reads the private `_task` once,
   with the reason in the docstring. Any other done-but-`RUNNING` worker
   raises rather than counting as done, so a future Textual change fails
   loudly instead of hanging or passing. The log
   re-reads the replacements automatically, since they are appended as they
   start. Their surviving work drains inside the same deadline. `ERROR`
   (`exit_on_error=False` keeps it off the app) is reported with the worker's
   error. Never `wait_for_complete()` with no arguments: `testing_conventions.md`
   names it the wrong tool, and it would wait on unrelated work.

   **The spy goes in `_make_app`.** Wrap `app.run_worker` as an instance
   attribute that delegates to the real bound method. Append the returned
   `Worker` to `app._test_render_workers` (a list initialised there) when
   `kwargs.get("group") in _RENDER_GROUPS`, and return it unchanged. Name check
   before writing: `_test_render_workers` must not exist on `App`/`MonitorApp`
   (`hasattr` probe). Import `WorkerState` from `textual.worker`.

2. **Stub the maintenance seam in `_make_app`:**
   `app._dispatch_refresh_maintenance = lambda: None`. Its docstring
   (`monitor_shared.py:630`) and `testing_conventions.md` ("A Textual `@work`
   worker left in flight…") say tests stub this method. Without the stub, every
   test refresh dispatches the real marks purge / session purge / sitrep
   harvest+refresh against `REPO_ROOT`: real subprocess work and CPU contention
   inside a test that claims no real tmux. No test in the module exercises
   maintenance (grep: no `maintenance`/`purge`/`sitrep` references).

3. **Make the not-inside-tmux precondition per-run and asserted.** Add
   `_no_tmux_env()`, a `contextlib.contextmanager` that wraps
   `unittest.mock.patch.dict(os.environ)` and pops `TMUX`/`TMUX_PANE` inside
   it. Use it around each `asyncio.run(runner())` in
   `MountedShadowColumnTests._run`, `_run_mounted`, and the three
   `NarrowFallbackTests` runners. Immediately after the mount pause in each
   runner, add `assert app._monitor is mon, "on_mount replaced the stubbed
   monitor (TMUX set?)"`, so a mis-path fails with its cause, never as a
   downstream `col.display` flake. Keep the import-time pop as well.

4. **Replace each single "let the deferred work land" `pilot.pause()` with
   `await _settle(app, pilot)`** in the module's mounted tests:
   - the mount pause in `MountedShadowColumnTests._run`, `_run_mounted` and the
     `NarrowFallbackTests` runners;
   - every `await app._refresh_data()` followed by `pause()`: the
     `KeyTargetingTests` / `TailFollowTests` wrappers, before `TailFollowTests`
     swaps `app.call_later`, so the drain uses the real one. Also every
     `MountedShadowColumnTests` method and the `NarrowFallbackTests` runners;
   - every pause after `.focus()`, `_apply_shadow_visibility(...)`,
     `_restore_focus(...)` and `pilot.resize_terminal(...)`. A double `pause()`
     collapses into one `_settle`.

5. **One precondition wait, in
   `test_full_refresh_renders_the_shadow_column_from_the_pane_list`:** after
   `app._pane_cards["%2"].focus()` + `_settle`, add
   `await _until(pilot, lambda: app._focused_pane_id == "%2", "focus to land on %2's card")`
   before the second `_refresh_data()`. This is the test's stated setup ("move
   the selection … so `_restore_focus` does not revert … underneath us"). The
   assertion that matters stays unchanged: the refresh must *keep* `%2` and
   render its shadow. `_until` is never used to wait on a final asserted
   condition, so a broken feature still fails at its own assertion.

6. **Add one test separating refresh rendering from selection rendering**,
   `MountedShadowColumnTests.test_refresh_rerenders_the_shadow_column_without_a_selection_change`.
   The existing `test_full_refresh_renders…` docstring claims "the 3s refresh
   must render the column", but the selection route also renders it, so that
   claim is not actually discriminated (see Verification 4). Steps:
   `app._focused_pane_id = "%1"`; refresh; `_settle`; assert the precondition
   `"shadow analysis line"` is shown. Record `before = app.focused`. Wrap
   `mon.capture_pane_content_async` so that `%9` returns
   `(pane, "shadow REFRESHED content")`, delegating to the original for
   everything else. Refresh; `_settle`. Then assert
   `app._focused_pane_id == "%1"`, and that `app.focused` is a `PaneCard` with
   `pane_id == "%1"`. Selection did not move, so the selection route had no
   reason to fire; asserted, not assumed. Finally
   `assertIn("shadow REFRESHED content", preview.render().plain)`. Its
   discriminating power is established by the Verification 4 control, not
   asserted here.

7. Update the module docstring's last paragraph. It says all ordering is
   deterministic through `_run_offloaded`. Add that mounted tests drain
   deferred UI work with `_settle` (ordering sentinel) rather than a bare
   `pilot.pause()`.

### Post-phase (risk mitigations)

1. [measure_loaded_flake_rate] Run Verification step 2 (loaded, interleaved,
   40 + 40) as a **blocking** gate before the Step 8 commit. Record exact
   per-side fail counts in the plan's Final Implementation Notes. Any failure
   on the fixed side means: capture its traceback, identify the unsettled
   deferral, extend `_settle` or the precondition waits, and re-run the
   measurement. Do not commit while the fixed side shows a failure.

## Verification

All measurement runs happen in a **scratch detached worktree** for the
baseline. The shared worktree is never stashed or restored. The worktree goes
in the session scratchpad: `git worktree add --detach <scratch>/base HEAD`.
`monitor_app.py` and the test file are unmodified at HEAD, so this is the
pre-fix state.

1. `python -m pytest -q -p no:xdist tests/test_monitor_shadow_zone.py`: all
   green, and the same as a script (`python tests/test_monitor_shadow_zone.py`).
2. **Loaded, interleaved flake measurement.** Run a CPU burner (cpu_count
   `python -c 'while 1: pass'` processes, killed by trap). Alternate 40 runs of
   the baseline module (scratch worktree) with 40 runs of the fixed module.
   Record exact fail counts per side. Expected: baseline > 0, fixed = 0. If the
   baseline produces 0 under load, report that the before/after contrast was
   not reproduced, and do not claim it.
3. **Supersession probe.** In the scratch worktree with the fixed test file,
   add a throwaway test (not committed). It mounts via `_run`, refreshes, then
   calls `app._update_shadow_preview()` twice back-to-back, so the second
   exclusive `shadow-preview` worker cancels the first, and then
   `await _settle(app, pilot)`. Pass condition: `_settle` returns well inside
   its deadline. At least one logged worker has `is_cancelled` true, which
   proves the case was hit, not merely tolerated. Record which shape occurred:
   `state CANCELLED`, or `RUNNING` with `task.cancelled()`. No exception. Then a second probe: start
   `app.run_worker(_boom(), group="preview", exit_on_error=False)` through
   the spy, where `async def _boom(): raise RuntimeError("probe")`. `_settle`
   must raise
   `AssertionError("preview render worker failed: …")`. Genuine failures stay
   reported.
4. **Negative controls (in the scratch worktree, with the fixed test file
   copied in).** Each must fail **at the test's own assertion**, not at a
   settle timeout, so check the traceback line:
   - mutate `_schedule_shadow_fit_check` to a no-op:
     `test_shadow_column_shown_and_sized_from_real_pane_width` must FAIL at
     `assertTrue(col.display)`;
   - **refresh-render control, against the new step-6 test.** Remove both
     PANE_LIST-path `self._update_shadow_preview()` calls: `_refresh_data`
     (`monitor_app.py:1204`) and the `_restore_focus` tail (`:1667`).
     `test_refresh_rerenders_the_shadow_column_without_a_selection_change`
     must FAIL at its `assertIn("shadow REFRESHED content", …)`. This control
     is **not** run against `test_full_refresh_renders…`. There, the selection
     render (`on_descendant_focus` → `_update_zone_indicators` →
     `_update_shadow_preview`, `monitor_app.py:2745`) supplies the content
     whatever the refresh does. A reviewer's probe confirmed that mutant
     passes that test. **If the mutant also passes the step-6 test** (a
     restore-driven re-focus still reaching the selection route), do not
     report the control as detected. Find which call rendered it (a
     `_update_shadow_preview` spy recording `inspect.stack()[1].function`),
     report it, and stop to ask the user before committing.
   - **Coverage boundary, stated rather than claimed:** step 5's precondition
     wait makes the second refresh save `%2`. So this test does **not**
     exercise `_restore_focus`'s t545 "respect the already-focused card"
     branch. A mutant removing that branch passes. No test in the repo covers
     that branch (grep for `t545` and its comment text in `tests/` finds
     nothing). Report it as an uncovered branch in the final notes. It was
     never this test's claim, and covering it means building a new test
     (focus moving between the refresh's save and its deferred restore),
     which is outside this flake fix.

   Remove the scratch worktree afterwards.
5. `bash tests/run_all_python_tests.sh` once. Read only the final
   `PYTHON SUITE:` line, using `set -o pipefail` if piped.

## Step 9

Post-implementation: commit the test file (`test: … (t2210)`), then archive via
Step 9 of the task workflow (current-branch mode, no merge).

## Risk

### Code-health risk: low
- Test-only change, confined to one module's fixtures and waits; production code is untouched. The maintenance stub removes behaviour no test in the module asserts. · severity: low · → mitigation: none

### Goal-achievement risk: low
- A rare flake cannot be proven absent by a finite run count: a deferral chain deeper than `_settle`'s 3 rounds, or a cause other than the two identified, would reappear at a lower rate. · severity: low (residual — addressed by inline post-phase measure_loaded_flake_rate) · → mitigation: inline post-phase measure_loaded_flake_rate

### Planned mitigations
- timing: post-phase | name: measure_loaded_flake_rate | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — rare flake not provably absent | desc: blocking loaded interleaved 40+40 flake measurement before commit; any fixed-side failure is diagnosed and fixed first

## Post-Review Changes

### Change Request 1 (2026-11-05)
- **Requested by user:** [timeout enforcement] `_until` checked its deadline only before an unbounded `await pilot.pause()`. Textual's `Pilot.pause` → `_wait_for_screen(timeout=30.0)` can block past the helper's 10s budget, and a predicate turning true during that await returned success with the budget already spent (reviewer probe: success after 0.103s with timeout=0.010s).
- **Changes made:** `_until` now bounds every pump with `asyncio.wait_for(pilot.pause(), remaining)`, rejects a success observed past the deadline, and reports elapsed time plus the budget left at entry in each failure (`timed out` / `pilot.pause() overran the remaining budget` / `condition held only past the deadline`). It also takes an absolute `deadline=`, which `_settle` passes in place of `timeout=remaining()`. Otherwise a near-zero remaining timeout would mark an already-true predicate as "past the deadline" spuriously.
- **Verification:** probes with a real pilot whose `_wait_for_screen` was delayed:
  - 0.1s delay, 0.01s budget, predicate flipped during the pump → RAISED at 0.010s;
  - 5s delay, 0.05s budget → RAISED at 0.050s;
  - 0.01s delay, 2s budget → SUCCESS.

  The supersession and failure probes were re-run and still pass (cancelled-before-start shape drained in 0.094s; failure still reported). Module: 41 passed (pytest and script). Loaded re-check of the fixed module: 0/20 failures, 12 burners.
- **Files affected:** `tests/test_monitor_shadow_zone.py`

## Final Implementation Notes
- **Actual work done:** All of it is in `tests/test_monitor_shadow_zone.py`, as planned.
  - Added `_until`, `_worker_done` and `_settle`, which drain deferred work by ordering. A `run_worker` spy in `_make_app` logs every `preview`/`shadow-preview` worker the app starts.
  - Stubbed `_dispatch_refresh_maintenance`.
  - Added a per-run `_no_tmux_env()` scrub and the `app._monitor is mon` mount assertion (`_STUB_REPLACED`) in `_run_mounted`, `MountedShadowColumnTests._run` and the three `NarrowFallbackTests` runners.
  - Replaced all 32 mounted-test `pilot.pause()` calls with `_settle`; three double pauses collapsed into one each.
  - Added the focus precondition wait in `test_full_refresh_renders…`.
  - Added `test_refresh_rerenders_the_shadow_column_without_a_selection_change`.
  - Updated the module docstring.
  - No production code changed, and no existing assertion was weakened.
- **Deviations from plan:**
  - The loaded measurement used 12 CPU burners (`nproc`/2), not `cpu_count`. The box was already at load 6–10 from concurrent agents, and 24 burners would have starved them. Measured load during the runs reached 18–27.
  - The baseline was a detached scratch worktree at HEAD `0eba599ab`, with this checkout's uncommitted `.aitask-scripts/` files (other sessions' work) copied in. Both sides therefore ran identical production code and differed only in the test file (checked with `diff -rq`).
  - The Post-Review Change Request 1 hardening of `_until` is recorded above.
- **Issues encountered:**
  - The task's diagnosis (mount-time `first_refresh` holding `_refresh_inflight`) does not apply under a plain run. The module pops `TMUX` at import, so `on_mount` takes the not-inside-tmux early return and `first_refresh` never starts.
  - The observed failure (`'%1' != '%2'`) and the `col.display` False failure both come from deferred `call_after_refresh` / `call_later` / exclusive-worker work that one CPU-idle `pilot.pause()` does not cover. The `TMUX`-replaces-the-stub exposure is guarded and asserted, but it was never observed.
  - Two design flaws caught in plan review were confirmed against Textual 8.2.7 and fixed:
    - `Worker.wait()` raises `WorkerCancelled` for a superseded exclusive worker.
    - A worker cancelled before `_run` begins stays `state=RUNNING` with `task.cancelled()`; the supersession probe hit exactly this shape.
- **Key decisions:**
  - The render-worker drain polls a spy log rather than calling `wait()` or snapshotting `app.workers`, which drops finished workers.
  - The new test separates refresh rendering from selection rendering: `on_descendant_focus` → `_update_zone_indicators` → `_update_shadow_preview` (`monitor_app.py:2745`) renders the shadow column whatever the refresh does.
  - `_until` takes an absolute `deadline=`, so `_settle`'s waits share one budget.
- **Verification evidence (durable):**
  - **Loaded, interleaved, 12 burners:** baseline 3/40 failed, fixed 0/40.
    - Baseline failures: run 7 `NarrowFallbackTests::test_on_resize_re_evaluates_on_a_fixed_preset` (False is not true); run 21 `MountedShadowColumnTests::test_grace_fallback_hands_the_post_fallback_zone_to_restore_focus` (PANE_LIST != PREVIEW); run 31 `test_on_resize…` again.
    - Two of the three were outside `MountedShadowColumnTests`, which justifies extending `_settle` to the module's other mounted classes.
  - **Unloaded repro before the fix:** 1/20 class runs failed, `'%1' != '%2'`.
  - **After Change Request 1:** loaded, fixed-only, 0/20.
  - **Supersession probe:** a logged worker reached `RUNNING`, `is_cancelled=True`, `task.cancelled()=True`, and `_settle` drained in 0.09s.
  - **Failure probe:** `_settle` raised `preview render worker failed: RuntimeError('probe')`.
  - **`_until` deadline probes (delayed `_wait_for_screen`):**
    - 0.1s delay against a 0.01s budget raised at 0.010s.
    - A 5s pump against a 0.05s budget raised at 0.050s.
    - An in-budget run succeeded.
  - **Negative controls (scratch copy):**
    - `_schedule_shadow_fit_check` made a no-op: `test_shadow_column_shown…` failed at `assertTrue(col.display)`.
    - Both PANE_LIST-path `_update_shadow_preview()` calls removed (`monitor_app.py:1204`, `:1667`): the new test failed at `'shadow REFRESHED content' not found`, and `test_full_refresh_renders…` passed, as predicted.
    - The `_restore_focus` t545 branch replaced with `if False:`: the whole module passed (41/41). That branch is **uncovered** by any test in the repo.
  - **Full Python suite:** `PYTHON SUITE: FAILED (runner=pytest, exit=1)`, with the single failure `tests/test_board_footer_multirow.py::BoardMultiRowFooterTests::test_fixture_facts` ("fixture must render footer keys"). It is unrelated: it passes alone and its whole module passes (10/10).
- **Upstream defects identified:**
  - `tests/test_board_footer_multirow.py:85 — test_fixture_facts asserts footer keys after a single pilot.pause(); under suite load the footer is not yet rendered (failed once in the full xdist suite, passes alone) — same CPU-idle single-pause race class as t2210`
