---
Task: t1487_bytrail_repeated_r_test_runs_real_reload_worker_into_teardow.md
Worktree: (current-branch mode — none)
Branch: (current-branch mode — none)
Base branch: main
Output branch: main
---

# t1487 — Stop board tests from running real `@work` workers into `run_test` teardown

## Context

`tests/test_board_bytrail_view.py::LaunchFallbackTests::test_repeated_R_during_an_in_flight_baseline_launches_once`
failed in 2 of 4 whole-suite parallel runs while passing alone. It was filed as a
launch-debounce timing flake. It is not one.

The test's assertions are deterministic by construction: both async seams
(`_trail_baseline_worker`, `_launch_trail`) are replaced with instance lambdas,
there is one `await pilot.pause()`, and no await sits between the later
assertions. What the test *does* leave running is a real Textual worker started
inside its own `run_test` block:

```
app._finish_trail_launch(["v1"], "", lambda: True)      # test:2180
  -> _after_trail_launch()                              # aitask_board.py:11376
  -> _reload_active_trail()                             # aitask_board.py:11115
  -> @work(thread=True) _trail_reload_worker            # aitask_board.py:11126
  -> load_trail_blob(handle)                            # real subprocess, 15s timeout
  -> app.call_from_thread(_on_trail_reload, ...)        # re-renders widgets
```

Two library facts turn that residue into a failure of the *enclosing* test:
`App.run_test` ends its `finally` with `if self._exception: raise self._exception`
(textual/app.py:2218, Textual 8.2.7), and `@work` defaults to
`exit_on_error=True`, so an errored worker routes through
`app._handle_exception(WorkerFailed(...))` (textual/worker.py:382-384). Any
exception in that worker — or in `_on_trail_reload`'s `_rerender_trail()` against
a tearing-down app — surfaces at the `async with` exit with a traceback nowhere
near the debounce assertions. **None of the board's 17 `@work` decorators sets
`exit_on_error`**, so every one of them is live under that default (the monitor
modules, by contrast, pass `exit_on_error=False` throughout).

Intended outcome: the named test proves its guard and starts no real worker; the
same shape is fixed everywhere the audit found it, with a per-test disposition;
and the failure mode is written down where a TUI test author meets it.

## Audit result (task item 2 — which-tests, not a boolean)

Scope swept: all 45 `tests/test_board_*.py` plus every module importing
`board_fixture` / `aitask_board` (57 modules).

**Unintentional — a real worker is live at `run_test` teardown. All four get fixed:**

| # | site | test | worker | extra residue |
|---|---|---|---|---|
| 1 | `test_board_bytrail_view.py:2140` (call at `:2180`) | `LaunchFallbackTests.test_repeated_R_during_an_in_flight_baseline_launches_once` | `_trail_reload_worker` (+ real `load_trail_blob` subprocess) | `_trail_launch_pending` left `True`; 2 captured-never-invoked baseline callbacks |
| 2 | `test_board_bytrail_view.py:2189` (call at `:2238`) | `LaunchFallbackTests.test_pending_guard_updates_the_rendered_footer` | `_trail_reload_worker`, identical mechanism | 1 uninvoked `then` in `pending` |
| 3 | `test_board_bytrail_view.py:2625`/`:2628` (helper `_double_tap@2589`, press at `:2614`) | `RefreshDoubleTapTests.test_double_tap_does_not_launch_in_{terminal,tmux}_mode` | `_trail_reload_worker` — the real dialog confirms, `_finish_trail_launch` → `_after_trail_launch()`; `_reload_active_trail` is absent from `_env`'s patch list | `_trail_watch_timer` installed and never `_stop_trail_watch()`ed |
| 4 | `test_board_marking.py:322` (call at `:329`) | `MarkGatingTests.test_binding_is_hidden_in_the_derived_views` | `_trail_discovery_worker` — the `bytrail` leg with `active_trail_handle is None` schedules `call_after_refresh(self._open_trail_select)` (`aitask_board.py:9776`); `discover_trails` unpatched | flips back to `"all"` without waiting |

**Deliberate — real workers on purpose, each already drained before block exit.
No change; recorded as the justification the AC asks for:**

- `test_board_bytrail_view.py:1841 ThreadWorkerTests` (5 tests) — exists to drive
  the real thread hop; each waits on its own `_wait()` poller and calls
  `_stop_trail_watch()`.
- `test_board_bytrail_view.py:2328 BannerRenderTests` — `_enter_live_bytrail@2343`
  deliberately leaves `_start_trail_drift` real; every test drains with
  `await app.workers.wait_for_complete()`.
- `test_board_bytrail_view.py:2106 test_baseline_read_is_off_the_ui_thread` — real
  `_trail_baseline_worker`, awaited via `_wait`.
- `test_board_bytrail_view.py:553`, `:3135`, `:3184`, `:3231`, `:3282` — real
  `_trail_discovery_worker` with the subprocess seam patched, each with an
  explicit poll loop.

**Structurally clean, no probe needed:** `ByTrailTestBase._enter_synthetic_bytrail`
(`:167-180`) bakes `app._start_trail_drift = lambda: None` into the shared entry
helper, so the drift worker is out of scope for every test that enters By-Trail
through it. `test_board_dialog_run_dispatch.py` / `test_board_work_report.py` call
unbound actions against a `MagicMock`; `test_board_dialog_subprocess_degrade.py`
runs worker bodies through `__wrapped__` — no Textual scheduling at all.

### Pre-phase (risk mitigations)

- **`enumerate_env_callers`** — before touching `RefreshDoubleTapTests._env`'s
  return signature, `grep -n "_env(" tests/test_board_bytrail_view.py` and list
  every caller (at least `_double_tap@2589` and
  `test_board_threads_the_resolved_key_through_normalisation@2633`). Then pick the
  shape — widen the returned tuple vs. return a small record — and update every
  caller in the same edit. Addresses the `_env` signature risk below.

## Step 1 — A shared probe in `tests/lib/board_fixture.py`

Both affected modules already use this harness, so the probe and its rationale
live with it rather than in four copies.

```python
def block_app_worker_starts(app) -> list:
    """Stand in for ``app.run_worker`` so no real ``@work`` worker can start.

    Returns the list that receives one **readable worker name** per attempted
    start. ``@work``'s wrapper calls ``self.run_worker(partial(method, …),
    name=name or method.__name__, …)`` (textual/_work_decorator.py:141-149), so
    the recorded string is the worker method's own name — deterministic, which is
    what lets a positive control assert on ``_trail_reload_worker`` specifically
    rather than on "it failed somewhere".
    """
    started = []

    def _record(work, *a, name="", **k):
        started.append(name or getattr(work, "func", work).__name__)
        # No Worker is created and None is returned: do not install this around
        # code that uses the returned Worker handle. Nothing on the paths below
        # does — `_reload_active_trail` and `_open_trail_select` both discard it.

    app.run_worker = _record
    return started
```

`@work` dispatches through `self.run_worker(partial(method, …), …)`
(`textual/_work_decorator.py:141`), and inside Textual only that decorator and
`Input`'s suggester ever call `run_worker` — so an instance-level stand-in on the
app is a precise, public-API choke point. **Scope-honest:** it covers workers
declared on `KanbanApp` only; `TaskDetailScreen._do_lock` / `_do_unlock` dispatch
through the *screen's* `run_worker` and are unaffected (no live-app test reaches
them). Install it *after* the fixture's synthetic entry so boot-time workers are
untouched.

Paired assertion on `FixtureBoardTestBase`:

```python
def assertNoLiveWorkers(self, app, started=None):
    """`started == []` is what discriminates; `len(app.workers)` is the AC probe.

    The `started` failure message MUST name the recorded workers, e.g.
    "real worker(s) started inside run_test: ['_trail_reload_worker']" — the
    positive control asserts on that name.
    """
```

Both halves are needed and neither is redundant: `WorkerManager._remove_worker` is
the worker's own done-callback, so `len(app.workers) == 0` is also what a worker
that started *and finished* leaves behind — it cannot, alone, prove none ran.
`started == []` proves that; `len(app.workers) == 0` catches anything started
before the stand-in went in. Note `await app.workers.wait_for_complete()` — the
only existing drain idiom in the suite — is the *wrong* tool here: it waits on the
very worker that raises. No test in the repo asserts on `app.workers` today, so
this is a new idiom, deliberately introduced.

## Step 2 — Fix the four sites

**#1 `test_repeated_R_during_an_in_flight_baseline_launches_once`** — follow the
idiom its sibling `test_direct_launch_fallback_installs_watch_and_reloads`
(`:2087-2088`) already uses: stub the reload and assert it was *requested*, so the
launch-once guard the test exists to prove is preserved rather than weakened.

```python
reloads = []                                               # (A)
app._reload_active_trail = lambda: reloads.append("reload") # (B)
started = bf.block_app_worker_starts(app)
...
app._finish_trail_launch(["v1"], "", lambda: True)
self.assertEqual(reloads, ["reload"])      # (C) pickup requested, not performed
...
# cleanup + probe, before the block exits
self.assertEqual(len(pending), 2)          # both captured, neither invoked
app._trail_launch_pending = False
pending.clear()
self.assertNoLiveWorkers(app, started)
```

**#2 `test_pending_guard_updates_the_rendered_footer`** — same two lines
(`_reload_active_trail` recorder + `block_app_worker_starts`), same closing probe.
Its `await pilot.pause()`es after `_finish_trail_launch` stay: they are what the
rendered-footer assertion needs.

**#3 `RefreshDoubleTapTests`** — add `patch.object(app, "_reload_active_trail", …)`
to `_env`'s patch list, recording into a `reloads` list returned alongside
`launches` (check `test_board_threads_the_resolved_key_through_normalisation@2633`
for a second `_env` caller before changing the signature). In `_double_tap`,
assert `reloads == []` while the double-tap is refused and `reloads == ["reload"]`
after the third press lands, then `app._stop_trail_watch()` and the probe inside
the `finally`.

**#4 `test_binding_is_hidden_in_the_derived_views`** — stub the selector before the
loop, the idiom already used at `test_board_bytrail_view.py:2296`:

```python
app._open_trail_select = lambda rescan=False: None
```

plus `block_app_worker_starts` / `assertNoLiveWorkers`. The test is about footer
gating; opening the real trail selector was never part of what it asserts.

## Step 3 — Record the failure mode

`grep -rn "WorkerFailed"` returns zero hits across `tests/`, `.aitask-scripts/`
and `aidocs/` — this is undocumented in-tree today.

- **`aidocs/framework/testing_conventions.md`** — new top-level `##` section
  carrying the rule: the two library facts with their file:line + Textual version,
  "a green assertion block is not evidence a test is isolated", the measured note
  that the exposure window is *total* (a probe delaying the worker's subprocess by
  8s showed app shutdown still waits for it), why `wait_for_complete()` is the
  wrong tool, and the stub-and-assert-requested remedy. Reference callers:
  `LaunchFallbackTests` (the fixed shape) and `ThreadWorkerTests` (the deliberate
  opposite). This file's own scope line is "rules for designing tests", and its
  threading checklist item 6 already carries the "assert the worker is gone, don't
  assume" axis.
- **`aidocs/framework/tui_conventions.md`** — a pointer line inside
  `### Verify in a real pty — a headless pin may not fail` (`:145`), where the
  reader is already thinking about `run_test`.
- **`tests/lib/board_fixture.py`** — a paragraph in the module docstring's
  `Fixture contract` section (ends `:103`, before the `Run:` footer) stating the
  obligation and naming `block_app_worker_starts`, plus the reverse
  `See aidocs/framework/testing_conventions.md, "<heading>"` reference — the
  bidirectional link this pair lacks today (idiom copied from
  `tests/lib/tmux_isolation.sh:101`).
- **`CLAUDE.md:314`** — widen the trigger beyond "threading / asyncio migration" to
  also fire on Textual `@work` / `run_test` tests, or the doc is never opened by
  the person writing a board test.

### Post-phase (risk mitigations)

- **`probe_positive_control`** — after the four fixes land, run **Verification
  step 2** (the canonical sequence; not restated here) and record both observed
  outputs in the Final Implementation Notes. This is a required step of this plan,
  not an optional check: a probe that stays green under that mutation proves
  nothing and must be redesigned before the task closes. Addresses the
  goal-achievement risk below.

## Verification

This section is the **single canonical home** for both control sequences; the
pre-/post-phase blocks above reference them by name and do not restate them.
Both controls use the same target test, `TARGET` =
`tests.test_board_bytrail_view.LaunchFallbackTests.test_repeated_R_during_an_in_flight_baseline_launches_once`.

1. **Negative control (AC2) — does the guard the test exists to prove still
   hold?** One mutation, in production code: delete `or self._trail_launch_pending`
   from `action_trail_refresh_agent` (`aitask_board.py:8984`). Run
   `python3 -m unittest $TARGET`; it must **fail on `len(launches) == 1`**
   (assertion message `2 != 1`), not on anything else. Revert. A passing negative
   control means the fix weakened the guard.

2. **Positive control (AC1) — can the new probe actually fail?** One mutation, in
   the test, and it must be **exactly** this: delete lines (A), (B) and (C) from
   the Step-2 `#1` sketch — the `reloads = []` binding, the
   `app._reload_active_trail = …` stub, and the `assertEqual(reloads, ["reload"])`
   assertion — and change nothing else. Deleting (B) alone is **not** a valid
   mutation: `reloads` stays `[]`, so the test fails at (C) with `[] != ['reload']`
   several assertions before the probe is reached; deleting (A)+(B) but keeping
   (C) raises `NameError` at the same place. Either way the probe is never
   exercised.

   With all three gone, the real `_reload_active_trail` runs and reaches
   `_trail_reload_worker`, whose `@work` wrapper hits the `block_app_worker_starts`
   stand-in. Nothing between `_finish_trail_launch` and the probe is affected —
   `_trail_launch_pending`, `check_action`, `launches` and `pending` all behave
   identically — so `assertNoLiveWorkers` is the **first and only** failure, and
   its message must name `_trail_reload_worker`. Confirm exactly that, then revert
   and re-run green.

3. `python3 -m unittest tests.test_board_bytrail_view tests.test_board_marking -v`.
4. `bash tests/run_all_python_tests.sh` — read **only** the last line
   (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); use `set -o pipefail` if
   piping, since `| tail` discards the status.

Step 9 (Post-Implementation) handles merge, gates and archival.

## Risk

Levels below are the **reassessment** after both confirmed mitigations were
inlined into the plan body (pre-phase + post-phase), per `risk-evaluation.md`.
Goal-achievement moved medium → low once `probe_positive_control` became a
required step rather than an optional verification check.

### Code-health risk: low
- The new `block_app_worker_starts` stand-in could make a test pass vacuously if it
  blocked a worker the test actually depends on · severity: low · → mitigation:
  inline post-phase `probe_positive_control` (the helper's own `started == []`
  assertion also turns that case into a loud failure rather than a silent pass,
  and every edited test keeps its original assertions)
- Changing `RefreshDoubleTapTests._env`'s return signature touches a second caller
  (`:2633`) · severity: low · → mitigation: inline pre-phase `enumerate_env_callers`
- No production code is modified at all; blast radius is 2 test modules, 1 test-lib
  helper and 3 doc files · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The reported intermittency was never reproduced locally (3x alone, 6x under 20
  CPU spinners, 2 full suites at `-n 4`, 2 at `-n 8`, all 18 `test_board_*` in one
  process — all green). Verification is therefore **structural** ("no real worker
  is started") rather than observational ("the flake stopped"), so a green suite
  after the fix is not by itself proof the reported failure is gone
  · severity: medium · → mitigation: inline post-phase `probe_positive_control`
- A path the audit missed would leave the same exposure elsewhere · severity: low
  · → mitigation: the audit swept all 57 board/fixture-importing modules and the
  complete `@work` inventory, and the four hits are recorded above with call sites

### Planned mitigations
- timing: pre-phase | name: enumerate_env_callers | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: `_env` return-signature change breaks its second caller | desc: enumerate every `_env` caller and pick the return shape before editing, updating all callers in one edit
- timing: post-phase | name: probe_positive_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: verification is structural, not observational — an unproven probe would leave the fix unverified | desc: mutate away the reload stub and confirm assertNoLiveWorkers fails naming _trail_reload_worker, then revert and re-run green, recording both outputs

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned, all four audited sites plus
  the shared probe and the four doc surfaces.
  - `tests/lib/board_fixture.py`: new module-level `block_app_worker_starts(app)`
    (records a readable worker name per attempted start via a stand-in on the app
    node's `run_worker`, and starts nothing) and
    `FixtureBoardTestBase.assertNoLiveWorkers(app, started=None)` (asserts
    `started == []` naming the recorded workers, plus `len(app.workers) == 0`).
    Added the `Fixture contract` docstring paragraph and the reverse
    `See aidocs/framework/testing_conventions.md, "<heading>"` reference.
  - `tests/test_board_bytrail_view.py`: fixes #1
    `test_repeated_R_during_an_in_flight_baseline_launches_once`, #2
    `test_pending_guard_updates_the_rendered_footer`, #3 `RefreshDoubleTapTests`.
  - `tests/test_board_marking.py`: fix #4
    `test_binding_is_hidden_in_the_derived_views`.
  - `aidocs/framework/testing_conventions.md` (new section),
    `aidocs/framework/tui_conventions.md` (pointer), `CLAUDE.md` (widened trigger).
- **Deviations from plan:** None structural. Two details worth recording:
  - The pre-phase `enumerate_env_callers` found exactly the two predicted `_env`
    callers (`_double_tap` at :2597 and
    `test_board_threads_the_resolved_key_through_normalisation` at :2646). Chose
    the widened 3-tuple `(launches, reloads, patches)` over a record, matching the
    sibling `_launch_env`'s existing 3-tuple shape at :1429. Both callers updated
    in the same edit.
  - The plan predicted the negative control would report `2 != 1`. It reports
    `3 != 1` — the test presses `R` twice more inside the pending window and,
    without the guard, BOTH launch. The failing assertion, its location and its
    message are exactly as specified; only my predicted count was wrong.
- **Issues encountered:** None. Both controls behaved as designed on the first
  attempt.
- **Key decisions:**
  - Stubbed the worker-*starting* method rather than the worker itself, so the
    launch-once guard each test exists to prove stays intact and the reload is
    asserted as *requested* (`reloads == ["reload"]`). This is the idiom the
    sibling `test_direct_launch_fallback_installs_watch_and_reloads` already used.
  - The probe is deliberately two-part. `len(app.workers) == 0` alone cannot
    discriminate: `WorkerManager._remove_worker` is the worker's own done-callback,
    so a worker that started *and finished* also leaves the set empty. The
    `started` recorder is what actually proves nothing ran; `len(app.workers)`
    is the AC-named probe and catches anything started before the stand-in.
  - Chose the app node's `run_worker` as the choke point: `@work` dispatches
    through `self.run_worker(partial(method, …), name=name or method.__name__)`
    (`textual/_work_decorator.py`), and inside Textual only that decorator and
    `Input`'s suggester call it — so the stand-in is precise and public-API.
    Scope is honest: it covers `KanbanApp`-declared workers only;
    `TaskDetailScreen._do_lock` / `_do_unlock` dispatch through the *screen's*
    `run_worker` and are untouched (no live-app test reaches them).
  - Doc home: `testing_conventions.md` for the rule (its scope line is "rules for
    designing tests" and its threading checklist item 6 already carries the
    "assert the worker is gone, don't assume" axis), with pointers from
    `tui_conventions.md` and `board_fixture.py`, and a widened `CLAUDE.md` trigger
    — without that widening the doc is never opened by someone writing a TUI test.

### Control results (both required, both observed)

- **Negative control (AC2).** Deleted `or self._trail_launch_pending` from
  `action_trail_refresh_agent` (`aitask_board.py`). Target test failed at the
  intended assertion:
  `AssertionError: 3 != 1 : a second agent was launched while the first baseline
  was still in flight` (test_board_bytrail_view.py:2183). Reverted via
  `git checkout --`; `git status --porcelain` on the file confirmed clean.
- **Positive control (AC1), the `probe_positive_control` post-phase.** Deleted
  lines (A) `reloads = []`, (B) the `app._reload_active_trail = …` stub and (C)
  the `assertEqual(reloads, ["reload"])` assertion — and nothing else.
  `assertNoLiveWorkers` was the **first and only** failure:
  `AssertionError: Lists differ: ['_trail_reload_worker'] != [] … real worker(s)
  started inside run_test: ['_trail_reload_worker']`. Reverted from a scratch
  backup; `LaunchFallbackTests` re-ran 6/6 green.
  Deleting (B) alone would NOT have been a valid mutation — the test would fail at
  (C) with `[] != ['reload']` before the probe is reached.

### Audit dispositions (AC3 — which-tests, not a boolean)

Swept all 45 `tests/test_board_*.py` plus every module importing `board_fixture` /
`aitask_board` (57 modules), against the full 17-entry `@work` inventory in
`aitask_board.py`. None of those 17 decorators sets `exit_on_error`, so all run
under Textual's `exit_on_error=True` default.

| test | worker | disposition |
|---|---|---|
| `test_board_bytrail_view.LaunchFallbackTests.test_repeated_R_during_an_in_flight_baseline_launches_once` | `_trail_reload_worker` | **fixed** — reload stubbed + probe; pending state and 2 uninvoked callbacks drained |
| `test_board_bytrail_view.LaunchFallbackTests.test_pending_guard_updates_the_rendered_footer` | `_trail_reload_worker` | **fixed** — same, + 1 uninvoked callback drained |
| `test_board_bytrail_view.RefreshDoubleTapTests.test_double_tap_does_not_launch_in_terminal_mode` | `_trail_reload_worker` | **fixed** — `_reload_active_trail` added to `_env`; `_stop_trail_watch()` in `finally` clears the leaked watch timer |
| `test_board_bytrail_view.RefreshDoubleTapTests.test_double_tap_does_not_launch_in_tmux_mode` | `_trail_reload_worker` | **fixed** — same helper |
| `test_board_marking.MarkGatingTests.test_binding_is_hidden_in_the_derived_views` | `_trail_discovery_worker` | **fixed** — `_open_trail_select` stubbed + probe |
| `test_board_bytrail_view.ThreadWorkerTests` (5 tests) | watch / reload / baseline | **deliberate** — exists to drive the real thread hop; each waits on its own `_wait()` poller and calls `_stop_trail_watch()` |
| `test_board_bytrail_view.BannerRenderTests` (`:2357`, `:2415`, `:2452`) | `_trail_drift_worker` | **deliberate** — `_enter_live_bytrail` leaves drift real on purpose; each drains with `await app.workers.wait_for_complete()` |
| `test_board_bytrail_view.test_baseline_read_is_off_the_ui_thread` | `_trail_baseline_worker` | **deliberate** — the point of the test; awaited via `_wait` |
| `test_board_bytrail_view` `:553`, `:3135`, `:3184`, `:3231`, `:3282` | `_trail_discovery_worker` | **deliberate** — subprocess seam patched, each with an explicit poll loop |

Structurally out of scope, recorded so it is not re-checked per test:
`ByTrailTestBase._enter_synthetic_bytrail` bakes `app._start_trail_drift = lambda:
None` into the shared entry helper, so the drift worker cannot leak from any test
entering By-Trail through it. `test_board_dialog_run_dispatch.py` /
`test_board_work_report.py` call unbound actions against a `MagicMock`;
`test_board_dialog_subprocess_degrade.py` runs worker bodies through `__wrapped__`
— no Textual scheduling at all.

- **Upstream defects identified:** None.
