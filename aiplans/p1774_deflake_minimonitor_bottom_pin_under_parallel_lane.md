---
Task: t1774_deflake_minimonitor_bottom_pin_under_parallel_lane.md
Base branch: main
Output branch: main
---

# t1774 — Deflake `test_minimonitor_bottom_pin.py` under the parallel lane

## Context

`tests/test_minimonitor_bottom_pin.py::DegenerateRangeTests::test_pinned_list_that_stops_overflowing_never_goes_negative`
failed at 97% of one full-suite run (`PYTHON SUITE: FAILED`), then passed 8/8
standalone and passed an immediate whole-suite re-run. Because the runner's last
line is the documented way to read the suite verdict, one load-sensitive module
makes that line untrustworthy for **every** change — this is a verdict-level
problem, not an annoyance.

t1725_3 spawned this task suspecting a generic "layout settles within a bounded
number of `pilot.pause()` calls" dependency, and suggested either a deterministic
settle or adding the module to the serial carve-out. **Neither is needed.** The
settle is already deterministic; the flake has one specific, measured cause.

### Root cause (reproduced through a documented seam)

`MiniMonitorApp._refresh_data` arms a **wall-clock fail-safe** on the
scroll-lock acquisition line (`.aitask-scripts/monitor/minimonitor_app.py:1618`):

```python
self._scroll_lock_timer = self.set_timer(
    self._SCROLL_LOCK_TIMEOUT, lambda: self._abandon_scroll_restore(gen)
)
```

`_SCROLL_LOCK_TIMEOUT` is **0.5 s** (`minimonitor_app.py:880`).
`_abandon_scroll_restore(gen)` **retires the generation**, so the
`call_after_refresh(self._restore_list_scroll, gen, 0)` scheduled a few lines
later returns immediately at its `gen != self._scroll_restore_gen` guard. For a
bottom-pinned list, `_restore_list_scroll` is the **only** caller of
`container._reconcile_anchor()` on the refresh path — the correction for the
compositor's unclamped container-branch write. Lose the restore and the
degenerate-range correction never happens, and `scroll_y` stays negative.

That is exactly the reported failure. Injecting the fault through the documented
seam (`mm.MiniMonitorApp._SCROLL_LOCK_TIMEOUT = 0.0001`) reproduces it verbatim:

```
AssertionError: -2 not greater than or equal to 0 : a pinned list that stopped
overflowing held a NEGATIVE scroll offset; the compositor's unclamped write was
not corrected
```

**Measured margin against the budget** (arm → restore-entry latency, 32 samples
across the whole module, same tree, this 24-core box):

| condition | min | max | budget |
|---|---|---|---|
| idle (loadavg ≈ 2.7) | 0.021 s | 0.050 s | 0.5 s |
| contended (loadavg ≈ 10.3) | 0.031 s | **0.249 s** | 0.5 s |

Moderate contention already eats **half** the budget. A 4-worker pool running
Textual apps, alongside the agents this box normally carries, crosses it.

### Blast radius: the sibling module shares the hazard

The same injection run against `tests/test_minimonitor_scroll_preservation.py`
— which owns the shared `_ListHost` / `_RefreshHost` / `_settle` fixture that
`test_minimonitor_bottom_pin.py` imports — fails 3 further tests
(`EarlyRestoreCallbackTests.test_anchor_restore_survives_an_early_restore_callback`,
`RestoreAcrossRefreshTests.test_mid_list_position_survives_a_refresh_tick`,
`RestoreAcrossRefreshTests.test_killed_anchor_lands_on_a_neighbour_not_at_the_top`),
plus `PinSurvivesRefreshTests.test_user_scroll_away_is_not_repinned` in the
reported module. So the fix belongs in the **shared host**, not in the one test
that happened to lose the race first.

`tests/test_minimonitor_bottom_pin_live.py` does **not** share the helper (it is
a real-tmux module with its own fixture) and stays in the serial carve-out
unchanged.

### Why the settle itself is not the problem

`_settle(pilot, frames)` is `frames × pilot.pause()`. Each pause runs
`_wait_for_screen()` (enqueue a `call_later` on every widget, wait for all to
drain — message-queue-driven, 30 s ceiling) and ends by calling
`screen._on_timer_update()`, which drains one batch of `call_after_refresh`
callbacks. The restore chain is 3 hops; `_settle`'s default of 12 frames covers
it with an order of magnitude to spare, **regardless of load**. Load does not
reduce the number of pumped frames — it only stretches wall-clock, which is
precisely why the one wall-clock element is the only thing that flakes.

`_scroll_lock_timer` is the **only** timer live in these fixtures: the app's
`set_interval` refresh timer (`minimonitor_app.py:1492`) sits behind `on_mount`'s
in-tmux branch, and both modules pop `TMUX`/`TMUX_PANE` at import.

## Approach

Take wall-clock out of the headless fixtures, and make the reason executable.
**No production code changes**, and **no serial carve-out change** — so
`CLAUDE.md`'s carve-out block and `tests/test_serial_carveout_doc_drift.sh` are
untouched.

## Implementation

### 1. `tests/test_minimonitor_scroll_preservation.py` — neutralise the budget in the shared host

Add a module-level constant immediately above `_ListHost` (currently line 197):

```python
#: The app's scroll-restore fail-safe (`_SCROLL_LOCK_TIMEOUT`, 0.5s) is the ONE
#: wall-clock element these headless fixtures reach, and it decides whether a
#: tick's `_restore_list_scroll` runs AT ALL: `_abandon_scroll_restore` retires
#: the generation, so the restore returns at its own `gen` guard and — for a
#: bottom-pinned list — `_reconcile_anchor` is never called. Measured on this
#: box the arm->restore latency runs 21-50ms idle and up to 249ms at loadavg 10,
#: against a 500ms budget; inside a loaded xdist pool it crosses (t1774).
#:
#: Everything else in these fixtures is pumped, not timed — `_settle` is N
#: `pilot.pause()` calls and each drains one `call_after_refresh` batch — so
#: making this budget non-binding makes the modules load-independent.
#:
#: This is NOT a bypass of the fail-safe's contract: it is still exercised at
#: the production value by
#: `LockLifecycleTests.test_failsafe_unlocks_and_retires_when_the_restore_never_runs`,
#: and `ScrollLockBudgetTests` below pins, in BOTH directions, that the budget
#: is what decides.
_NON_BINDING_SCROLL_LOCK_TIMEOUT = 3600.0
```

Inside `_ListHost`, add the override with a one-line pointer (not a restatement)
back to the constant.

Extend the module docstring with a short paragraph naming t1774, the mechanism,
and the two tests that keep it honest.

### 2. Same file — keep the fail-safe's own test on the production budget

`LockLifecycleTests.test_failsafe_unlocks_and_retires_when_the_restore_never_runs`
(lines 626-665) is the only reader of `app._SCROLL_LOCK_TIMEOUT` in the suite. It
must opt back in, and it must stop depending on a fixed sleep margin:

- Set `app._SCROLL_LOCK_TIMEOUT = mm.MiniMonitorApp._SCROLL_LOCK_TIMEOUT` on the
  instance before `await app._refresh_data()` — **derived from the production
  constant**, never a duplicated literal, so the test keeps exercising the real
  budget.
- Move the `locked_immediately` read to immediately after
  `await app._refresh_data()` returns, ahead of `_settle(pilot, 4)`. Nothing
  clears the lock in between (the restore stub is a no-op), so this is the same
  assertion against a strictly shorter window.
- Replace `await asyncio.sleep(app._SCROLL_LOCK_TIMEOUT + 0.3)` — a fixed margin
  that is the same defect class this task is fixing — with a **bounded poll**:
  pump `pilot.pause()` until `not app._list_scroll_lock`, or until a generous
  wall-clock deadline (10 s) expires. The deadline fails only if the fail-safe
  genuinely never fires, which is the contract under test.

Every assertion and its message stays byte-identical.

### 3. Same file — new `ScrollLockBudgetTests`, the executable reason

A `_RefreshCase` subclass placed next to `LockLifecycleTests`, asserting **both
directions** of the toggle.

**It must not depend on which of two independent loop tasks runs first.**
Textual's `Timer._run` sleeps in its own asyncio task and then invokes the
callback directly; `_restore_list_scroll` runs from a `call_after_refresh` on the
screen refresh. Nothing orders them, so a bare tiny timeout would leave this new
discriminating test able to flake itself — the defect class it exists to remove.

**Ordering barrier — a `_hold_restore` helper.** It follows
`EarlyRestoreCallbackTests._with_early_first_restore`'s interception shape
(instance-level `app.call_after_refresh` override, match on
`callback == app._restore_list_scroll`, restored in `finally`), but **holds** the
tick's first restore instead of firing it early:

- Wrap `app._abandon_scroll_restore` on the instance to record every call that
  carries a `gen`. The fail-safe lambda (`minimonitor_app.py:1619`) looks the
  method up at call time, so the wrapper sees it. The only other gen-bearing call
  site (`:1955`, the restore's own `NoMatches` branch) is inside the held restore
  and cannot run while it is held — so a recorded gen-bearing call **is** the
  fail-safe.
- Capture the tick's `(gen, attempt)` instead of scheduling the restore.
- On release, invoke the real restore with the captured args and record whether
  it scheduled `_release_list_scroll_lock` for that gen. Both restore branches
  (pinned and mid-list) schedule it; the gen guard and the `state is None` return
  schedule nothing — so "scheduled a release" is a branch-agnostic witness that
  the restore ran past its guards.

The two cases:

- **binding budget** — the tiny-timeout scenario is kept
  (`app._SCROLL_LOCK_TIMEOUT = 0.0001`). Run one tick with the restore held, then
  **wait for the observed fail-safe transition**: pump `pilot.pause()` until the
  recorded gen-bearing abandon call names the captured gen **and**
  `app._scroll_restore_gen > captured gen`. A 10 s deadline bounds the wait; it
  fails only if the timer genuinely never fires, with a message saying so. Only
  then release the restore, and assert it scheduled **no** release — it was
  refused.
- **fixture budget** (the host default) — the same held tick; pump a fixed
  `_settle(pilot, 4)`; assert **no** gen-bearing abandon call was recorded and the
  generation is unchanged. At 3600 s the ordering cannot flip, so this case needs
  no barrier. Release, and assert the restore **did** schedule the release for its
  gen.

Both cases first assert that a restore was actually captured, or the case is
vacuous.

The refusal is observed from the **real restore's behaviour**, not from the
generation comparison the barrier waited on, so the binding case is not
tautological. It shows that the 0.0001 s timer really fires while the restore is
pending, and that the restore is then refused.

It asserts the **cause** (the restore is refused once the fail-safe has retired
its generation), not the symptom (a negative `scroll_y`). Pinning the symptom would make a benign
production behaviour the contract and would block a future improvement that
corrects the degenerate range without the restore; pinning the cause states
exactly why the fixture neutralises the budget and nothing more.

Docstring records the production consequence explicitly so it is not mistaken
for a defect being papered over: if the fail-safe wins in production, the list
holds a negative offset until the **next** refresh tick, which re-captures
`pinned=True`, restores and reconciles. It self-heals within one refresh
interval; only a test that drives exactly one tick can observe it.

### 4. `tests/test_minimonitor_bottom_pin.py` — docstring only

Add a note under "WHAT THIS MODULE CAN AND CANNOT DISCRIMINATE" stating that the
module inherits the neutralised budget from the shared host, that the fail-safe's
own contract lives in the sibling module, and that this is why the module is not
in the serial carve-out. No code change.

### Post-phase (risk mitigations)

- **parallel_lane_soak** — after steps 1-4 land and verification steps 1-3 and 5
  pass, run `bash tests/run_all_python_tests.sh` **3 times consecutively**
  (this replaces verification step 4's single run). For each run, capture the
  exit status via `${PIPESTATUS[0]}` (never through a bare pipe) and record the
  verdict line, the lane banner's worker count, and whether
  `test_minimonitor_bottom_pin.py` or `test_minimonitor_scroll_preservation.py`
  appears in any failure. All three must read `PYTHON SUITE: PASSED`. A failure
  in an **unrelated** module is reported as such, with its test id, and does not
  count against this fix; a failure in either target module means the fix is
  incomplete — stop and re-investigate rather than retry. Addresses the
  goal-achievement risk below.

## Verification

Run from the repo root; read only the runner's **last** line for a suite verdict,
and never through a bare pipe (`set -o pipefail` / `${PIPESTATUS[0]}`).

1. **Both modules, clean:**
   `python -m pytest tests/test_minimonitor_bottom_pin.py tests/test_minimonitor_scroll_preservation.py -v`
   → 8 + 31 + the new cases, all pass.
2. **Both modules under contention** — 48 spinners, ≥5 consecutive repetitions of
   the two modules. Every repetition must pass. (Pre-fix, the same loop passes
   too — CPU load alone was not enough to reproduce; this is a regression floor,
   not the discriminating check.)
3. **Discriminating check — the symptom, in both directions, with no file
   mutated.** Run a script from the scratchpad directory. It edits no tracked
   file, so there is nothing on disk to revert and no `git restore` in a shared
   worktree. The script imports both test modules and drives the
   `DegenerateRangeTests` scenario (pin, shrink to 2 cards, one tick) through the
   `_hold_restore` barrier:
   - **binding budget** — an in-process override
     `_ListHost._SCROLL_LOCK_TIMEOUT = 0.0001`, restored in `try/finally`.
     Release the restore only after the observed fail-safe transition, settle,
     and assert the **behavioural condition** `scroll_y < 0`, not a specific
     number. The magnitude depends on layout: the module docstring records -2 in
     this fixture and -8 on a bare `VerticalScroll`.
   - **fixture budget** — assert `scroll_y >= 0`.
   Both must hold. This proves the regression the fixture change removes,
   independently of the new test, which pins the cause, not the symptom.
4. **Full parallel lane — 3 consecutive runs** (the `parallel_lane_soak`
   post-phase above): each verdict line `PYTHON SUITE: PASSED (runner=pytest, …)`,
   with the lane banner confirming `-n <workers> --dist loadfile` and the module
   in the **pool**, not the carve-out.
5. **Carve-out doc guard unchanged:** `bash tests/test_serial_carveout_doc_drift.sh`
   → PASS (no carve-out edit was made; this confirms nothing drifted).

## Post-implementation

Step 9 (Post-Implementation) owns cleanup, archival and merge.

## Risk

### Code-health risk: low

- Neutralising a wall-clock guard in a **shared** fixture could mask a future
  regression in which the restore chain genuinely never completes — the tests
  would then wait rather than fail fast. · severity: low · → mitigation: already
  covered — `LockLifecycleTests.test_lock_and_snapshot_clear_after_every_tick`
  asserts, per tick, that the lock is released and the snapshot cleared, so a
  restore that never completes still fails loudly; the fail-safe's own contract
  still runs at the production value (step 2), and `ScrollLockBudgetTests`
  (step 3) pins that the budget is the deciding variable.
- Test-only change, two modules, no production file touched; the sibling live
  module does not share the fixture. · severity: low · → mitigation: none needed
- A discriminating test that forces the race through a tiny timer can flake
  itself if nothing orders the timer ahead of the restore (raised in plan
  review). · severity: high before the fix, low after · → mitigation: core plan
  step 3 — the `_hold_restore` observed-transition barrier. This is part of the
  design, not a separate mitigation.

### Goal-achievement risk: medium

- The in-situ parallel-lane failure was **never reproduced directly** — only
  through the documented `_SCROLL_LOCK_TIMEOUT` seam. The evidence (identical
  assertion and value, the only wall-clock element in the path, a measured 5x
  margin degradation under moderate load) is strong but circumstantial. If a
  second, rarer cause exists, the module can still flake. · severity: medium ·
  → mitigation: inline post-phase parallel_lane_soak

Reassessed once against the augmented plan (inline mitigation confirmed): the
level stays **medium**. Three green runs raise confidence but cannot prove a
rarer cause absent, so the soak narrows this risk without retiring it.

### Planned mitigations
- timing: post-phase | name: parallel_lane_soak | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: medium | addresses: goal-achievement — in-situ parallel-lane failure never reproduced directly | desc: Run the full parallel-lane Python suite 3x consecutively after the fix and report each verdict
