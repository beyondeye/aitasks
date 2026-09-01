---
Task: t1660_minimonitor_startup_input_latency_fails_in_parallel_lane_aft.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1660 — minimonitor startup input-latency test fails in the parallel lane

## Context

`test_minimonitor_startup_input_latency.py::MountWindowProbeTests::test_mount_returns_while_the_window_probe_is_still_blocked`
started failing inside the `-n 4 --dist loadfile` lane after t1653 (`451dd3af7`),
with `key took 822.3ms` / `595.3ms` against a `INPUT_BUDGET_S / 2` = 500 ms budget,
while passing in 0.41 s standalone. t1660 asks which of two mechanisms is at work —
a real input-latency regression from t1653, or an already-marginal wall-clock
assertion pushed over its budget — because the two have opposite fixes and
raising the budget would erase the signal if it were the first.

**Verdict: marginal assertion. Not a regression.** Evidence below. The fix is to
change the *instrument*, per the t1510 precedent (`aiplans/archived/p1510_*.md:47-53`),
not the threshold.

### Evidence — the assertion does not measure input latency

Measured with the real test under `~/.aitask/venv/bin/python` (textual 8.2.7):

| quantity | idle box | 24-way CPU load |
|---|---|---|
| true input latency (`driver.send_message` → `App.on_event`) | **0.23 ms** | — |
| `Pilot._wait_for_screen()` (app queue drain) | 4.0 + 2.5 ms | 14.8 ms |
| `wait_for_idle` inside `App._press_keys` | **188.2 + 20.1 ms** | (exceeded the 1 s outer `wait_for` → `TimeoutError`) |
| whole `pilot.press("j")` — what the assertion times | 215 ms (43 % of budget, zero contention) | > 1000 ms |

Two independent terms, neither of which is input dispatch:

1. **Textual's idle-sampling harness.** `Pilot.press` → `App._press_keys`
   (`textual/app.py`) calls `await wait_for_idle(0)` **twice per key**, plus
   `animator.wait_until_complete()` twice. `wait_for_idle` (`textual/_wait.py`)
   compares `process_time()` against wall clock in 20 ms `sleep` granules — a
   ≥20 ms floor per call and a `max_sleep=1` cap, so ≥40 ms and up to **2 s** per
   key, decided by the scheduler. Profiled on an **idle** box, the first call ran
   338 ms wall / 253 ms CPU, waiting on Textual's own mount+layout work
   (`screen._refresh_layout` 127 ms, `tui_switcher.on_mount` 83 ms).
2. **The key under test is not inert.** `j` is bound to `action_tui_switcher`
   (`.aitask-scripts/monitor/minimonitor_app.py:1077` → `lib/tui_switcher.py:1465`),
   which pushes a **65-widget `TuiSwitcherOverlay`**. `Pilot._wait_for_screen()`
   then posts a `call_later` to all 65 and waits for every one. The timed region
   therefore includes mounting the screen the keypress opens.

The file's own rationale for choosing `press` over `pause` — *"`pilot.press`
awaits `_wait_for_screen()`, which is event-driven with no sleep"*
(`tests/test_board_movement.py:693-698`, echoed at
`test_minimonitor_startup_input_latency.py:188-190`) — is **false in textual 8.2.7**:
`press` carries strictly *more* `wait_for_idle` than `pause` (two calls vs one).

### Evidence — t1653 contributes nothing to this path

Two independent A/Bs agree:

- **In-process neutralisation** of every t1653 addition (`MiniPaneList.on_mount`,
  `on_resize`, `_reconcile_anchor`, `_check_anchor`, `_on_scroll_to`,
  the `vertical_scrollbar` override) — `wait_for_idle` wall 184 / 157 / 151 ms and
  CPU 55 / 62 / 82 ms across HEAD → neutralised → HEAD. Run-to-run variance exceeds
  the with/without difference, and the neutralised arm is not consistently faster.
- **Code trace.** `MiniPaneList.on_mount` runs once on an empty container:
  `anchor()` → `scroll_end(immediate=True, animate=False)` starts no animation and
  no `Timer`, and with `allow_vertical_scroll` False assigns no reactive, so there
  is no extra layout pass. `MiniPaneScrollBar.__init__` is called **0 times** (the
  list never overflows, so the lazy scrollbar is never built). Widget count on
  screen is **7, identical** before and after t1653. Total t1653 contribution: **2
  no-op `InvokeLater` messages** on the `MiniPaneList` queue before the keypress.
  `_check_anchor` / `_on_scroll_to` / `MiniPaneScrollBar` are never reached.

What t1653 *did* change is lane load: it added `tests/test_minimonitor_bottom_pin.py`
(387 lines) to the parallel pool. A scheduler-decided wall-clock upper bound sitting
at 43 % of budget with **zero** contention is exactly what more lane load tips over.

A stray `@work` worker (`aidocs/framework/testing_conventions.md:40-53`, the failure
mode that impersonates a timing flake) is ruled out: the reported failure is the
`assertLess` message itself, not a re-raised worker exception.

## Approach

Replace the wall-clock upper bound with a **contention-invariant, clock-free**
observation of the property it was proxying for: *the key reaches `App.on_event`
while the probe is still blocked*. Count **event-loop turns**, not seconds — load
only changes how long a turn takes, never how many are needed.

Validated in-process before writing this plan:

| | idle | 24-way load |
|---|---|---|
| turns to dispatch, fixed code | 3–4 (n=10) | 3–4 (n=10) |
| turns to dispatch, regression injected (`run_worker` → `call_later`, probe awaited inline on the pump) | **never dispatched, 200-turn cap hit** | — |

66× headroom, deterministic in both directions, and the regression now fails in
sub-millisecond time instead of after a 1 s timeout.

This follows the repo's ranked precedent — counter/structural over wall clock
(`test_board_manager_moves.py:268`, `test_board_group_focus.py:938`,
`test_board_fixture_harness.py:539`) — and the rejected alternatives are rejected
for the reasons already recorded: **raising the budget** (t1510 "Suggested fix":
trades one arbitrary threshold for another), **retries/sleeps**
(`testing_conventions.md:35-38`), and **the serial carve-out** (explicitly
not for `App.run_test` modules — `tests/test_stats_backlog_panes_live.py:16-20`).

## Implementation

Steps 1-5 are confined to **`tests/test_minimonitor_startup_input_latency.py`**.
The post-phase adds one docstring-only edit to `tests/test_board_movement.py`.
**No production code changes anywhere.**

### 1. New module-level helper, next to `INPUT_BUDGET_S` (~line 101)

```python
#: Event-loop turns allowed for a key to reach `App.on_event`. A COUNT, not a
#: duration: contention changes how long a turn takes, never how many are needed.
#: Measured 3-4 turns identically on an idle box and under 24-way CPU load; with
#: the probe awaited inline on the pump the key never arrives at all, so the cap
#: is exhausted. 200 is ~50x the observed cost.
_DISPATCH_TURNS = 200


async def _press_and_observe(app, key: str, seen: list) -> int | None:
    """Send `key` the way Textual's own Pilot does, and count TURNS to dispatch.

    Deliberately NOT `pilot.press()`. In textual 8.2.7 `Pilot.press` ->
    `App._press_keys` awaits `wait_for_idle(0)` TWICE per key (a >=20ms floor
    each, capped at 1s each) plus `animator.wait_until_complete()`, and then
    `Pilot._wait_for_screen()` posts a `call_later` to every widget on screen and
    waits for all of them -- 65 of them once `j` pushes `TuiSwitcherOverlay`.
    Measured on an IDLE box, that harness cost was 208ms of a 215ms `press`,
    against a 500ms budget, while the property under test -- send to
    `App.on_event` -- cost 0.23ms. Timing `press` measured the harness (t1660).

    `driver.send_message` is the same call `_press_keys` makes; only the idle
    sampling around it is dropped.
    """
    event = events.Key(key, key if len(key) == 1 else None)
    event.set_sender(app)
    app._driver.send_message(event)
    for turn in range(1, _DISPATCH_TURNS + 1):
        if seen:
            return turn
        await asyncio.sleep(0)
    return None
```

Add `from textual import events` to the imports.

**Plus a machine-readable diagnostic seam**, so the contention control produces
comparable evidence instead of ad-hoc `print`s (the `AITASK_BOARD_ATTR_VERDICT_LOG`
precedent in `tests/test_board_movement.py`). Both tests call it once, after their
assertions:

```python
#: Optional path; when set, each dispatch observation appends one TSV line
#: `<test name>\t<turns or "EXHAUSTED">\t<mount_elapsed_ms or "">`. Off by default,
#: so the suite is unchanged; the contention control (post-phase 1) sets it.
_DISPATCH_LOG_ENV = "AIT_MINIMON_DISPATCH_LOG"


def _log_dispatch(name: str, turn: int | None, mount_ms: float | None = None) -> None:
    path = os.environ.get(_DISPATCH_LOG_ENV)
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"{name}\t{turn if turn is not None else 'EXHAUSTED'}\t"
                 f"{'' if mount_ms is None else f'{mount_ms:.2f}'}\n")
```

Writing it **after** the assertions is deliberate: a failing run still records its
`EXHAUSTED` line only if the assertion order is preserved, so put the `_log_dispatch`
call inside the same `try` block, before the asserts, and assert afterwards. That way
the log is written on both outcomes and a failed control is visible in the log.

### 2. `FirstRefreshDispatchTests.test_a_keypress_is_dispatched_while_the_first_refresh_is_stalled` (lines 187-207)

Replace the timed region — `t0 = perf_counter()`, the `asyncio.wait_for(pilot.press("j"), …)`,
`latency = …`, and the `assertLess(latency, INPUT_BUDGET_S / 2, …)` — with:

```python
turn = await _press_and_observe(app, "j", handled)
self.assertIsNotNone(
    turn,
    f"the keypress never reached App.on_event within {_DISPATCH_TURNS} "
    f"event-loop turns while the first refresh was in flight — it is back "
    f"on the message pump",
)
self.assertIn("j", handled, ...)          # kept verbatim
```

Keep the surrounding `try/finally` that releases `mon.gate`, the trailing
`await pilot.pause()` and the `assertFalse(app._refresh_inflight, …)` unchanged.
The `>= 1` / bubble-up comment above `assertIn` stays.

### 3. `MountWindowProbeTests.test_mount_returns_while_the_window_probe_is_still_blocked` (lines 562-591)

- **Keep** `mount_elapsed` and its `assertLess(mount_elapsed, INPUT_BUDGET_S / 2, …)`
  (line 576). It wraps a *synchronous* `app.on_mount()` — no event loop, no Pilot,
  no `wait_for_idle`. Measured 0.18-0.26 ms idle and 0.47-8.8 ms under 24-way load:
  a ≥57× margin at the worst loaded sample. Add a one-line comment saying exactly
  that, so the next reader knows why this budget survived while the press budget
  did not.
- Replace the press-timed region (581-591) with the same `_press_and_observe`
  block as §2, message naming *"while the mount probe was in flight"*.
- After the `finally: _StalledTmuxClient.gate.set()`, add an **untimed**
  `await pilot.pause()` before the `run_test` block exits, mirroring the sibling
  test. `j` pushes the 65-widget `TuiSwitcherOverlay`; with the press no longer
  waiting for it, teardown can otherwise race the mount (observed as
  `ScreenStackError: No screens on stack` from `on_key` while building this plan).

### 4. Correct the now-false rationale in the module docstring (lines 41-44)

Rewrite *"The budget is a hard `asyncio.wait_for` … rather than something a loaded
CI can lose"* — it was lost. State instead that dispatch is asserted as a **turn
count**, that `pilot.press` is not a latency instrument in textual 8.2.7 and why,
and keep **"Assert on input dispatch, never on loop lag"** (now literally true).
Delete the stale "NEVER pilot.pause() in a timed region" comment at 188-190 — there
is no timed region left there, and its premise was wrong about `press` anyway.

### 5. Positive-control table (docstring, lines 46+)

Three distinct rows, with **three distinct failure modes**. Do not collapse them —
the existing `subprocess.run` row does **not** become a turn-exhaustion control.

**(a) Relabel — two existing rows, same mutation, new failure mode.** These two both
target `test_a_keypress_is_dispatched_while_the_first_refresh_is_stalled`, whose timed
region is being replaced, so their "must fail" text changes from `TimeoutError` to
*turn exhaustion*:

| mutation | must fail |
|---|---|
| `_start_monitoring` back to `self.call_later(self._refresh_data)` | that test, by **turn exhaustion** (the key never reaches `App.on_event` within `_DISPATCH_TURNS`) |
| `self.set_timer(0, self._refresh_data)` instead of `run_worker` | the same test, same way — `set_timer` wraps the callback in `call_next`, which drains inline and JUMPS the queue |

**(b) Leave alone — the existing mount row keeps its current mutation and its current
failure mode.** `on_mount`'s window probe back to `subprocess.run` fails because the
stalled fake is **never consulted**, so `_StalledTmuxClient.entered` is never set and
`await asyncio.wait_for(entered.wait(), timeout=5)` raises — the test dies *before*
the dispatch observation is ever reached. That row is unaffected by this change and
its "must fail" text must **not** be rewritten to say turn exhaustion.

**(c) Add — a new row, because (b) cannot exercise the new instrument.** Without this,
`test_mount_returns_while_the_window_probe_is_still_blocked` has **no** positive
control for the turn-count observation. The mutation must let the probe **enter**
(so `entered.wait()` succeeds) and only *then* block the App message pump:

> In `MiniMonitorApp.on_mount` (`.aitask-scripts/monitor/minimonitor_app.py:1303-1309`),
> replace
> `self.run_worker(self._seed_own_window_info(), name="own_window_seed", …)`
> with
> `self.call_later(lambda: self._seed_own_window_info())`.
>
> `call_later` posts an `events.Callback` to the **App's own queue**, which
> `MessagePump.on_callback` awaits INLINE in the App's message loop. The probe runs,
> `_StalledTmuxClient.run_async` sets `entered` and then awaits the gate — so
> `entered.wait()` succeeds from the test's own task while the pump stays blocked
> inside the probe. The key is then never dispatched.
>
> The lambda is required: `call_later` takes a **callable**, not a coroutine — passing
> the coroutine directly raises `TypeError: the first argument must be callable` and
> would be a bogus control that fails for the wrong reason.

| mutation | must fail |
|---|---|
| `on_mount`'s `run_worker(…, name="own_window_seed", …)` → `self.call_later(lambda: self._seed_own_window_info())` | `test_mount_returns_while_the_window_probe_is_still_blocked`, by **turn exhaustion** — the probe enters, then holds the App pump |

Reproduced in-process while planning: fixed code dispatched at turn 3-4 in every
trial; this mutation hit the 200-turn cap with `handled == []` in every trial.

### Post-phase (risk mitigations)

Runs after step 5 and before the Verification block is signed off.

1. `[contention_control]` Run the module under a **bounded, self-cleaning** CPU load
   and confirm the turn count does not move. Exactly this, from the repo root:

   *(the command is a top-level block below — see **Contention control command**)*

   **The step is passed only if the whole pasted command exits 0** — check `$?`, or
   read the `contention control exit=` line. No printed banner is the verdict: `echo`
   returns 0 from either branch *and* would swallow the subshell's status, so the
   status is captured into `rc` the instant the subshell closes, echoed, and then
   re-raised by a bare `(exit "$rc")`. The subshell is what makes `exit` safe to
   paste into an interactive shell. Every failure path sets `status` — a failed trial, a surviving
   tracked burner, a stray burner, a missing/short row set, an `EXHAUSTED` row, or a
   turn count that differs from the idle baseline. Nothing is swallowed by an
   `|| echo`, and the `pgrep` result is consumed by an `if`/`elif`, not by a branch
   that succeeds either way.

   The validator compares against the **idle baseline TSV** rather than a hardcoded
   `3-4` band: the claim being tested is *invariance*, and pinning a literal would
   also make a benign shift in the implemented helper look like a regression.
   `mount_elapsed` is deliberately **recorded but not bounded** here — adding a
   wall-clock ceiling to the control would reproduce the very defect this task fixes.

   - **5 trials**, 24 burners (one per core on this box — `nproc` = 24; scale to
     `nproc` elsewhere and say so in the notes), 180 s burner budget so the loop
     cannot outlive the trials.
   - **Cleanup is mandatory and enforced, not just printed.** A surviving tracked
     PID or a stray burner sets `status`, so it reaches the exit code; the
     `burners clean` line is a convenience for the human reading the output, and the
     exit status is what decides. Leftover burners would silently corrupt the two
     full-suite runs in Verification step 1, so this step runs **after** those two
     runs, never before.
   - **Record in the Final Implementation Notes**, verbatim from `$LOG`: a row per
     trial per test — `test name | turns | mount_elapsed ms` — plus the idle-box
     baseline from Verification step 2 for comparison, and the `nproc`/`uptime`
     load figures for both. Expected: every loaded row's turn count **identical to
     the idle baseline row** for the same test (measured 3-4 while planning, but the
     validator compares, it does not pin a literal).
   - A turn count that **moves with load**, or any `EXHAUSTED` row, falsifies the
     contention-invariance premise this whole fix rests on. Report it and stop —
     do not widen `_DISPATCH_TURNS` to absorb it.
2. `[report_residual_flakes]` If either full-suite run (Verification step 1)
   fails in a module **other than** `tests/test_minimonitor_startup_input_latency.py`,
   do **not** re-run until green and do **not** attribute it here. Record the
   module, the assertion, and the verbatim failure output in the Final
   Implementation Notes, and hand each one to its owning task (spawn a task where
   none exists). State explicitly in the notes whether t1660's own acceptance
   criterion was met independently of those failures.
3. `[correct_press_rationale_in_board_movement]` Correct the false rationale in
   `tests/test_board_movement.py` — `_sample()`'s docstring at :693-698 ("`pilot.press`
   awaits `_wait_for_screen()`, which is event-driven with no sleep") and, if it
   repeats the claim, `_floor()`'s at :756-765. Replace with what 8.2.7 actually
   does: `Pilot.press` -> `App._press_keys` awaits `wait_for_idle(0)` **twice per
   key** (>=20 ms floor each, 1 s cap each) plus `animator.wait_until_complete()`,
   so `press` carries strictly *more* harness cost than `pause`; `_floor()` is what
   keeps the benchmark's ratios honest, and it remains necessary for that reason.
   **Docstring/comment text only — change no code, no constant and no assertion in
   that file**, so its benchmark numbers are untouched. Cross-reference t1660.
   Verify with `~/.aitask/venv/bin/python -m pytest tests/test_board_movement.py -q`
   (or the module standalone) to confirm nothing regressed.

### Contention control command

Kept **unindented at top level on purpose**: this block contains a `<<'VALIDATE'`
heredoc, whose terminator must sit at column 0. Indented under a list item it is
copied with leading spaces and never closes — verified: `bash -n` reports
*"here-document delimited by end-of-file"*. Copy it from here, not from a
reflowed quote of it.

```bash
(                                  # subshell: `exit` below must not kill your shell
LOG=$(mktemp); status=0; pids=()
for _ in $(seq 1 24); do
  ~/.aitask/venv/bin/python -c 'import time
t = time.time()
x = 0
while time.time() - t < 180: x += 1' &
  pids+=($!)
done
trap 'kill "${pids[@]}" 2>/dev/null' EXIT   # cleanup even on an aborted run
sleep 2
for trial in 1 2 3 4 5; do
  AIT_MINIMON_DISPATCH_LOG="$LOG" \
    ~/.aitask/venv/bin/python tests/test_minimonitor_startup_input_latency.py \
    || { echo "TRIAL $trial FAILED"; status=1; }
done
kill "${pids[@]}" 2>/dev/null; wait 2>/dev/null; trap - EXIT
for p in "${pids[@]}"; do
  if kill -0 "$p" 2>/dev/null; then echo "BURNER $p STILL RUNNING"; status=1; fi
done
if pgrep -f 'while time.time() - t < 180' >/dev/null; then
  echo "STRAY BURNERS STILL RUNNING"; status=1
elif [ "$status" -eq 0 ]; then
  echo "burners clean"
fi
~/.aitask/venv/bin/python - "$LOG" /tmp/idle.tsv 5 <<'VALIDATE' || status=1
import collections, sys
loaded_path, idle_path, trials = sys.argv[1], sys.argv[2], int(sys.argv[3])

def rows(path):
    out = []
    for line in open(path, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if len(f) >= 2:
            out.append((f[0], f[1]))
    return out

baseline = dict(rows(idle_path))       # from Verification step 2, one run
loaded = rows(loaded_path)
bad = []
if not baseline:
    bad.append(f"idle baseline {idle_path} is empty — rerun Verification step 2")
if not loaded:
    bad.append(f"{loaded_path} is empty — no dispatch was ever logged")
counts = collections.Counter(name for name, _ in loaded)
for name in baseline:
    if counts[name] != trials:
        bad.append(f"{name}: {counts[name]} rows, expected {trials}")
for name, turn in loaded:
    if turn == "EXHAUSTED":
        bad.append(f"{name}: EXHAUSTED — the key was never dispatched under load")
    elif name not in baseline:
        bad.append(f"{name}: no idle baseline row to compare against")
    elif turn != baseline[name]:
        bad.append(f"{name}: {turn} turns under load vs {baseline[name]} idle — "
                   "the turn count MOVED with load; contention-invariance, the "
                   "premise this whole fix rests on, is falsified")
for b in bad:
    print("CONTENTION CONTROL VIOLATION:", b)
sys.exit(1 if bad else 0)
VALIDATE
cat "$LOG"
if [ "$status" -eq 0 ]; then echo "CONTENTION CONTROL: PASSED"
else echo "CONTENTION CONTROL: FAILED"; fi
exit "$status"                     # the verdict, not just the banner
); rc=$?                             # capture BEFORE anything else clobbers $?
echo "contention control exit=$rc"
(exit "$rc")                         # re-raise it: `echo` above returned 0
```

## Verification

1. `bash tests/run_all_python_tests.sh --test-dir tests` → last line must read
   `PYTHON SUITE: PASSED`. **Run it twice on an idle box** — a standalone module
   run proves nothing here (p1500 precedent, `aiplans/archived/p1500_*.md:326-340`).
   Use `set -o pipefail` if piping; the exit status is otherwise `tail`'s.
2. `rm -f /tmp/idle.tsv && AIT_MINIMON_DISPATCH_LOG=/tmp/idle.tsv ~/.aitask/venv/bin/python tests/test_minimonitor_startup_input_latency.py`
   — the module standalone on an idle box (check `uptime` first). The `rm` matters:
   `_log_dispatch` appends, so a second run without it would leave two rows per test
   in the baseline. Keep the TSV; it is what the contention control compares against.
3. **The positive controls from §5, by hand, each reverted afterwards.** They do
   **not** share a failure mode — check each against its own row, and treat a
   control that fails for the *other* reason as a failed verification:
   - `_start_monitoring` → `call_later` — must fail `test_a_keypress_is_dispatched_…`
     by **turn exhaustion**.
   - `_start_monitoring` → `set_timer(0, …)` — same test, same way.
   - `on_mount`'s probe → `subprocess.run` — must fail
     `test_mount_returns_while_the_window_probe_is_still_blocked` at the
     **`entered.wait()` timeout** (and `test_on_mount_issues_no_synchronous_subprocess`
     by name). *Not* turn exhaustion — the dispatch observation is never reached.
   - `on_mount`'s `run_worker(…)` → `self.call_later(lambda: self._seed_own_window_info())`
     — must fail the same test by **turn exhaustion**, having first got *past*
     `entered.wait()`. This is the only control that exercises the new instrument on
     the mount path; if it fails at `entered.wait()` instead, the mutation was
     mis-applied.
4. **Contention control** — post-phase step 1 above (5 trials, 24 burners, verified
   cleanup, TSV recorded). Run it *after* step 1's two full-suite runs. This is the
   check that would have caught the original defect.
5. `bash tests/test_serial_carveout_doc_drift.sh` — unchanged, but cheap proof the
   carve-out was deliberately *not* touched.

## Risk

### Code-health risk: low

- The same false `pilot.press` rationale still stands in `tests/test_board_movement.py:693-698`,
  so a reader who trusts it can reintroduce exactly this defect in a new timed
  region. · severity: low (residual — addressed by inline post-phase
  `correct_press_rationale_in_board_movement`) · → mitigation: inline post-phase
  `correct_press_rationale_in_board_movement`
- The helper reaches `app._driver.send_message`, a Textual private API, under a
  `textual>=8.2.7,<9` pin that floats within major 8; a shape change there breaks
  the test. Accepted: it is the same call `App._press_keys` makes, it fails loudly
  (`AttributeError`) rather than silently, and the helper docstring records why it
  is used. · severity: low · → mitigation: none
- Blast radius is one test file plus a docstring-only edit in a second, and zero
  production files; the replacement assertion was proven to fail on the injected
  regression before this plan was written. · severity: low · → mitigation: none
- **New (introduced by the inline phases):** post-phase step 3 edits a file owned by
  the board-benchmark work rather than by t1660, so this task's diff now spans two
  test modules. Bounded by the step's own "docstring/comment text only, no code, no
  constant, no assertion" constraint and its standalone-run check. · severity: low
  · → mitigation: none

### Goal-achievement risk: medium

- Acceptance requires a green **full suite**, repeatably. This change removes the
  only assertion observed to fail, but a full-suite verdict is a claim about every
  module — another lane-sensitive module could keep the criterion unmet through no
  fault of this fix. · severity: medium (residual — addressed by inline post-phase
  `report_residual_flakes`, which makes the attribution explicit rather than
  removing the exposure) · → mitigation: inline post-phase `report_residual_flakes`
- The new instrument's contention-invariance is the load-bearing claim, and it was
  established while planning rather than by the delivered test run. · severity:
  low (residual — addressed by inline post-phase `contention_control`) · →
  mitigation: inline post-phase `contention_control`
- `mount_elapsed` stays a wall-clock upper bound. Its margin is ≥57× at the worst
  loaded sample, but it is the same *class* of instrument, so a later flake there
  would make this fix look incomplete. · severity: low · → mitigation: covered by
  the §3 comment recording the measured margin, so a future reader can re-decide
  with data rather than re-deriving it

### Planned mitigations
- timing: post-phase | name: contention_control | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the instrument's contention-invariance is only established from planning-time measurements | desc: re-run the module under 24 background CPU burners and record the loaded turn counts and mount_elapsed samples
- timing: post-phase | name: report_residual_flakes | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — "full suite green" is a claim about every module, not just this one | desc: record any non-t1660 full-suite failure verbatim, hand it to its owning task, and state whether t1660's own criterion was met independently
- timing: post-phase | name: correct_press_rationale_in_board_movement | type: documentation | priority: low | effort: low | inline_risk: low | added_complexity: medium | addresses: code-health — the same false pilot.press rationale invites the defect to be reintroduced | desc: docstring-only correction of the "event-driven with no sleep" claim in tests/test_board_movement.py, changing no code or assertion

---

## Implementation notes (as-built)

### Deviations from the approved plan

1. **Assertion order swapped, and the key drain moved INTO the `finally`.** The plan
   put `assertIn("j", handled)` first and the untimed `await pilot.pause()` *after*
   the `try/finally`. Running positive control (a) proved both wrong:

   > `textual.app.ScreenStackError: No screens on stack` — raised from
   > `MiniMonitorApp.on_key` (`minimonitor_app.py:2528`, `isinstance(self.screen, …)`)

   On the **failure** path the assertions raise before the plan's trailing `pause()`,
   so the queued Key was still pending at `run_test` teardown; the pump then dispatched
   it after the screen stack was gone, and `run_test`'s `raise self._exception` MASKED
   the real assertion with a traceback nowhere near it — the exact
   `testing_conventions.md:40-53` hazard. Fix: `await pilot.pause()` now lives inside
   the `finally`, right after the gate release, so it drains on both paths. The turn
   assertion also now precedes `assertIn`, so a control reports turn exhaustion **by
   name** rather than the older, vaguer message. Both tests, symmetrically.

2. **Positive-control row (b) corrected rather than relabelled.** The plan assumed
   `set_timer(0, self._refresh_data)` would newly fail by turn exhaustion. Measured: it
   fails at the `mon.entered.wait()` timeout — the first refresh does not run at all
   within the 5 s window, so the test dies *before* the dispatch observation. Verified
   this is **unchanged by t1660** by running the same mutation against the pre-t1660
   test file recovered with `git show HEAD:…` (same `TimeoutError`, 5.49 s). The row
   now states its true failure point instead of claiming a mode it never had.

### Positive controls — all four run by hand, source restored (md5 verified)

| control | observed failure | time |
|---|---|---|
| (a) `_start_monitoring` → `call_later(self._refresh_data)` | `AssertionError: unexpectedly None : … never reached App.on_event within 200 event-loop turns` | 0.06 s |
| (b) `_start_monitoring` → `set_timer(0, …)` | `TimeoutError` at `mon.entered.wait()` (pre-existing; see deviation 2) | 5.29 s |
| (c) `on_mount` probe → `subprocess.run` | `TimeoutError` at `_StalledTmuxClient.entered.wait()` **and** `test_on_mount_issues_no_synchronous_subprocess` by name (`['subprocess.run (line 1307)'] != []`) | 5 s |
| (d) `on_mount` `run_worker` → `call_later(lambda: self._seed_own_window_info())` | `AssertionError: unexpectedly None : … within 200 event-loop turns while the mount probe was in flight` | 0.29 s |

Each reverted from a scratchpad snapshot (never `git restore` — the tree is shared);
`md5sum` confirmed `minimonitor_app.py` byte-identical to its pre-mutation state after
every control.

### Module results

- `~/.aitask/venv/bin/python tests/test_minimonitor_startup_input_latency.py` — **18
  tests OK in 0.53 s** (was 0.51 s for a subset; the `pilot.press` harness cost is gone).
- Idle baseline `/tmp/idle.tsv`: both tests dispatch at **turn 4**;
  `mount_elapsed = 0.47 ms`.
- `pytest tests/test_board_movement.py -q` — **32 passed, 2 skipped** (the 2 are the
  env-gated benchmarks) after the docstring-only post-phase edit.

### [report_residual_flakes] Full-suite run 1 — 2 failures, neither t1660's

`bash tests/run_all_python_tests.sh --test-dir tests` → `PYTHON SUITE: FAILED
(runner=pytest, exit=1)`; `2 failed, 6271 passed, 2 skipped in 290.12s`. The serial
carve-out phase passed (11 passed). Verbatim:

```
FAILED tests/test_board_gate_digest_budget.py::SharedGatePredicateContractTest::test_each_predicate_has_exactly_its_two_consumers
  AssertionError: Items in the first set but not the second: '_build_gate_fields'
FAILED tests/test_collection_parity.py::CollectionParityTests::test_backends_collect_the_same_per_file_counts
  AssertionError: ['test_aitask_merge: unittest=96 pytest=0',
                   'test_merge_union_characterization: unittest=5 pytest=0'] != []
```

**Attribution: a concurrent session editing this working tree mid-run — not t1660.**
Evidence, not inference:

- t1660 touches exactly two files, `tests/test_minimonitor_startup_input_latency.py`
  and `tests/test_board_movement.py`. Neither appears in either failure.
- mtimes: `.aitask-scripts/board/aitask_merge.py` **15:37:35**,
  `tests/test_board_gate_digest_budget.py` **15:34:55**, `.aitask-scripts/aitask_gate.sh`
  **15:34:02** — all *inside* the suite window (15:32-15:37). t1660's own files:
  15:25.
- `git status` shows ~20 uncommitted modifications absent at this session's start
  (`aitask_gate.sh`, `aitask_board.py`, `aitask_merge.py`, `gate_ledger.py`,
  `settings_app.py`, the `task-workflow` goldens, …).
- Both failures are **not reproducible**: `pytest tests/test_board_gate_digest_budget.py
  tests/test_collection_parity.py -q` → **18 passed**. `pytest=0` for
  `test_aitask_merge` was a transient collection error while `aitask_merge.py` was
  being written; it collects 96 now.

Per this mitigation's own rule, these were **not** re-run until green and are **not**
attributed here. They belong to whoever is editing the gate-digest / merge code — the
`_build_gate_fields` predicate is new work in flight, not a regression.

**t1660's own acceptance was met independently of these two**: every t1660-touched
module is green, and the failing assertions are in files this task never opened.
