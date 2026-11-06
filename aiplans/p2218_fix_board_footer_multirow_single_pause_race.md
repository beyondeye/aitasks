---
Task: t2218_fix_board_footer_multirow_single_pause_race.md
Base branch: main
Output branch: main
---

# t2218 — Wait for the board footer by ordering, not one pause

## Context

`BoardMultiRowFooterTests::test_fixture_facts` failed once in a loaded full xdist
run with `[] is not true : fixture must render footer keys`. It passes alone. The
test mounts `KanbanApp`, does one `await pilot.pause()` (which is
`wait_for_idle(0)` and depends on CPU idleness, not ordering), then queries
`FooterKey`.

**Mechanism (verified in the Textual 8.2.7 source):**

- `Footer.compose()` yields nothing until `_bindings_ready`.
- `_bindings_ready` is set only by `Footer.bindings_changed`, which subscribes to
  `screen.bindings_updated_signal`.
- `Screen.refresh_bindings()` publishes **synchronously**. It runs from
  `_watch_focused`, `_watch_stack_updates`, and the app's own
  `refresh_bindings()`.
- `bindings_changed` then queues a recompose:
  `self.call_after_refresh(self.recompose)`. That is an `InvokeLater` on the
  **footer's own** FIFO pump.
- `recompose()` is async: `await remove()`, then `await mount_all()`. The footer
  is empty in between.
- `MultiRowFooter.on_resize` (`.aitask-scripts/lib/multirow_footer.py:336`)
  queues another recompose after a height change. That recompose is terminal:
  it keeps the same height and content.
- Screen after-refresh callbacks run sequentially and each one is awaited
  (`Screen._invoke_and_clear_callbacks`).

So after mount, focus, blur or a view switch, the footer can be in one of three
states until its recompose chain has drained:
- never composed: empty;
- mid-recompose: empty or partial;
- stale: an earlier composition.

Two board deferrals feed that chain.

**Startup focus:**
- Path: `on_mount` → `call_after_refresh(_claim_startup_focus)` →
  `target.focus()` → `call_later(set_focus)` (`aitask_board.py:2800`, `:3905`).
- `BoardScreen.AUTO_FOCUS = ""`, so `app.focused is not None` proves that the
  startup claim has landed.
- Exposure: if the claim lands after a test's own `focus()` or `set_focus(None)`,
  it overrides that call.

**View switch (`_set_base_filter("bytopic")`, `aitask_board.py:3715`):**
- `base_filter` is assigned synchronously, so waiting on it orders nothing.
- `refresh_board` then:
  1. calls `remove_children()`;
  2. mounts `TopicColumn`s;
  3. queues `call_after_refresh(apply_filter)`;
  4. queues `call_after_refresh(_refocus_card, <prev focused filename>)` →
     `card.focus()` → `call_later(set_focus)`.

  `_set_base_filter` also ends with a synchronous `self.refresh_bindings()`.
- `apply_filter` and `_refocus_card` are both queued on the app's FIFO, in that
  order. So focus landing on a card inside a `TopicColumn` is the traced
  completion point of the view chain.
- For `move_to_column` in bytopic, `check_action` returns False from
  `base_filter` alone (`aitask_board.py:2645-2662`). Any composition built after
  the switch therefore reflects the asserted state.

**Exposure across the class:**

| test | exposure |
|---|---|
| `test_fixture_facts` | reported failure (empty footer) |
| `test_the_footer_wraps_at_200_columns` | height read before recompose → false fail |
| `test_no_footer_key_is_clipped` | empty footer → **vacuous pass** at each width |
| `test_the_four_previously_hidden_keys_reach_the_rendered_footer` | stale/empty footer after `focus()`; a late startup claim → false fail |
| `test_check_action_gating_still_reaches_the_footer` | `NotIn` on an empty footer passes vacuously; a late startup claim re-shows the binding after the blur; stale footer after the view switch |
| `test_the_overflow_hint_names_the_editor_key_the_footer_shows` | no hint/keys yet → false fail |

`test_the_board_mounts_the_multi_row_footer` is not exposed: the widget is
composed synchronously and `can_focus` is static. It stays unchanged, as do the
four tests that only check `BINDINGS`.

**Intended outcome:**
- Every mounted footer read happens only after a positive readiness witness.
- All existing assertion lines stay byte-identical.
- The waits cover only preconditions and ordering, never the final asserted
  condition. A broken feature still fails at its own assertion.

## Implementation (single file: `tests/test_board_footer_multirow.py`)

1. **`_until(pilot, predicate, what, *, timeout=…, deadline=None)`**
   - Copy it verbatim from t2210 (`tests/test_monitor_shadow_zone.py:191-225`).
     It bounds each `pilot.pause()` with `asyncio.wait_for`, rejects a success
     observed past the deadline, and its `AssertionError` names `what`.
   - Add a one-line comment saying it mirrors t2210's helper.
   - Keep it local: moving it into `tests/lib` would mean editing t2210's module.
   - Constants: `_SETTLE_TIMEOUT = 10.0`, `_QUIET_ROUNDS = 2`.

2. **Recompose counters.**
   - Save the original at module level: `_ORIG_RECOMPOSE = MultiRowFooter.recompose`.
   - `async def _counting_recompose(self)`:
     - bumps `self._test_recompose_started`;
     - awaits `_ORIG_RECOMPOSE(self)`;
     - bumps `self._test_recompose_finished` in a `finally`.

     Both counters use `getattr(…, 0)` defaults.
   - `BoardMultiRowFooterTests.setUp`:
     `patcher = mock.patch.object(MultiRowFooter, "recompose", _counting_recompose)`,
     `patcher.start()`, `self.addCleanup(patcher.stop)`.
   - The class patch takes effect because `call_after_refresh(self.recompose)`
     resolves the bound method at call time.
   - Names are already probed: `dir(MultiRowFooter)` shows only `recompose` and
     `_check_recompose`. Re-probe at implementation time with `hasattr` over the
     MRO.
   - Add `_started(app)` / `_finished(app)` accessors over
     `app.query_one(MultiRowFooter)`.

3. **`_footer_ready(app, pilot, *, since=None, timeout=_SETTLE_TIMEOUT, _on_pending=None)`**, the
   single readiness helper. It runs under one shared deadline. Pseudocode:
   ```python
   deadline = loop.time() + timeout
   quiet, witnessed, keys = 0, since is None, False

   def _not_ready(reason):
       keys_now = bool(list(app.query(FooterKey)))   # state AT the failure, never a stale snapshot
       return AssertionError(
           f"footer not ready ({reason}): quiet={quiet} witnessed={witnessed} keys={keys_now} "
           f"started={_started(app)} finished={_finished(app)} since={since}")

   while True:
       before = _started(app)
       fired = []
       footer.call_after_refresh(fired.append, True)   # FIFO behind any recompose already queued on the footer's pump
       try:
           await _until(pilot, lambda: bool(fired), "footer after-refresh sentinel", deadline=deadline)
       except AssertionError as exc:                   # a bounded-wait timeout keeps the readiness diagnostic
           raise _not_ready(f"sentinel wait: {exc}") from exc
       started, finished = _started(app), _finished(app)
       quiet = quiet + 1 if (started == before and finished == started) else 0
       witnessed = since is None or started > since
       keys = bool(list(app.query(FooterKey)))
       if quiet >= _QUIET_ROUNDS and witnessed and keys:
           if loop.time() > deadline:
               raise _not_ready("ready only past the deadline")
           return
       if _on_pending is not None:                     # test-only: observe a round that declined to return
           _on_pending(quiet=quiet, witnessed=witnessed, keys=keys)
       if loop.time() > deadline:
           raise _not_ready("timed out")
   ```
   Every failure route raises one `footer not ready (...)` message carrying the
   live `keys=` / `quiet=` / `witnessed=` state. That includes a timeout inside
   the sentinel `_until`.

   `_on_pending` runs only on rounds where the helper **decided not to return**,
   after the exit check. It changes no behaviour and exists so step 6 can
   observe a pending helper deterministically.
   It returns only when all three exit conditions hold together:
   - **quiet:** no recompose started or in flight for two consecutive
     sentinel-ordered rounds;
   - **witnessed:** a recompose started after the caller's trigger snapshot;
   - **non-empty:** `FooterKey`s are present **in the settled state**, not
     before settling.

   A populated → empty recompose therefore keeps the helper pumping until the
   deadline, and then raises naming `keys=False`. It never returns into a
   vacuous loop.

   Sentinel rounds also run after a repaint, so the final composition's layout,
   regions and height are current when it returns.

4. **Board-level waits**, built on step 3.
   - **`_board_ready(app, pilot)`:**
     1. `_until(TaskCard present, "task cards to mount")`;
     2. `_until(app.focused is not None, "board startup focus to land")`;
     3. `_footer_ready(app, pilot, since=0)`, which needs at least one
        recompose.
   - **`_focus_and_settle(app, pilot, widget)`:**
     1. `was = app.focused`, `snap = _started(app)`;
     2. call the focus trigger (`widget.focus()`, or `app.screen.set_focus(None)`
        when `widget is None`);
     3. `_until(app.focused is widget, "focus to land on …")`;
     4. `_footer_ready(app, pilot, since=snap if was is not widget else None)`.
        If focus did not change, there is no new recompose to witness.
   - **View switch,** inline in the gating test:
     1. `snap = _started(app)`;
     2. `app._set_base_filter("bytopic")`;
     3. `_until(app.focused is a TaskCard with a TopicColumn ancestor, "bytopic refocus to land")`.
        That is the traced end of the chain: `apply_filter` runs before it in
        the same FIFO.
     4. `_footer_ready(app, pilot, since=snap)`.

     `TopicColumn` comes from `self.ab.TopicColumn`. Check during implementation
     that the module exposes it.

5. **Call sites.**
   - Replace each post-mount `await pilot.pause()` in the six exposed tests with
     `await _board_ready(app, pilot)`. In `test_no_footer_key_is_clipped` this
     runs at each width.
   - Replace each `focus()` / `set_focus(None)` + pause with
     `_focus_and_settle`.
   - Replace the bytopic switch + pause with the step 4 view-switch sequence.
   - Assertion lines stay byte-identical. In `test_fixture_facts` the
     existing `assertTrue` lines remain after `_board_ready`.

6. **Two committed helper tests,** in a new class
   `FooterReadinessHelperTests` with the same base and `setUp` patch, so the
   readiness logic is pinned and not just argued:
   - **`test_readiness_rejects_a_footer_emptied_after_it_was_populated`:**
     1. `_board_ready`.
     2. Set the instance attribute `footer.compose = lambda: iter(())`.
        `compose(self)` calls `self.compose`, so the next recompose yields no
        keys.
     3. `snap = _started(app)`, then `footer.call_after_refresh(footer.recompose)`.
     4. `with self.assertRaisesRegex(AssertionError, r"footer not ready .*keys=False"): await _footer_ready(app, pilot, since=snap, timeout=1.5)`.
        This matches whichever route timed out, sentinel wait or loop deadline,
        because both raise through `_not_ready`.

     It then checks it is not vacuous: `assertGreater(_finished(app), snap)`,
     so the emptying recompose really completed.
   - **`test_readiness_stays_pending_while_the_bindings_update_is_withheld`.**
     The producer is coordinated explicitly, with no timers and no dependence
     on pace:
     1. `_board_ready`, then `snap = _started(app)`.
     2. Create `pending = asyncio.Event()` and `seen = []`. Define
        `on_pending(**s)`: `seen.append(s)`; then `pending.set()` once
        `len([x for x in seen if x["quiet"] >= _QUIET_ROUNDS and x["keys"] and not x["witnessed"]]) >= 2`.
     3. `task = asyncio.create_task(_footer_ready(app, pilot, since=snap, _on_pending=on_pending))`.
        The update is **withheld**: nothing calls `refresh_bindings`.
     4. `done, _ = await asyncio.wait({task, asyncio.create_task(pending.wait())}, timeout=_SETTLE_TIMEOUT, return_when=FIRST_COMPLETED)`.
     5. Assert `task not in done` ("readiness returned while the update was
        withheld"), assert `pending.is_set()`, and assert `_started(app) == snap`.
        The helper has now declined to return on at least two rounds that were
        quiet and non-empty, solely for lack of the witness.
     6. **Release:** `app.refresh_bindings()`.
     7. `await asyncio.wait_for(task, _SETTLE_TIMEOUT)`, then assert
        `_started(app) > snap` and `_finished(app) == _started(app)`.
     8. Cancel the leftover waiter in a `finally`.

     With the witness removed, the helper returns on the first quiet non-empty
     round. `on_pending` therefore never fires, `task` lands in `done`, and step
     5 fails, however slowly the pumps run. The step 6 test drives
     `_footer_ready` from a second task while the test coroutine itself only
     awaits. Only one coroutine pumps the pilot at a time.

7. **Module docstring:** one sentence. Mounted footer reads go through
   `_board_ready` / `_footer_ready`, which combine a footer-pump ordering
   sentinel, recompose counters, a trigger witness and a non-empty settled
   footer, rather than a bare `pilot.pause()` (t2218).

### Post-phase (risk mitigations)

1. **[measure_loaded_flake_rate]** A **blocking** gate before the Step 8 commit.
   - Baseline: a scratch detached worktree,
     `git worktree add --detach <scratchpad>/base HEAD`. The test file is
     unmodified at HEAD, so this is the pre-fix state. Never stash or restore
     the shared tree.
   - Start `nproc` CPU burners (`python -c 'while 1: pass'`, killed by a trap).
   - Interleave 30 runs of the baseline module with 30 runs of the fixed module:
     `python -m pytest -q -p no:xdist tests/test_board_footer_multirow.py`,
     each from its own tree.
   - Record exact per-side fail counts in Final Implementation Notes.
   - A failure on the fixed side blocks the commit: capture the traceback,
     identify the unsettled deferral, extend the waits, and re-measure.
   - If the baseline shows 0 failures, report that the contrast was not
     reproduced and do not claim it. The step 6 helper tests are the
     deterministic evidence that does not depend on reproducing the flake.

## Verification

1. Run `~/.aitask/venv/bin/python -m pytest -q -p no:xdist tests/test_board_footer_multirow.py`.
   It must be green, and the same as running the file as a script. The step 6
   tests run here.
2. Run the post-phase loaded measurement.
3. **Negative controls.** Run each in the scratch worktree with the fixed test
   file copied in, and check the traceback line.
   - Flip `move_to_column` to `show=False` in the board `BINDINGS`.
     `…reach_the_rendered_footer` must fail **at `assertIn(action, rendered)`**,
     not at a readiness timeout.
   - Make `check_action` return True for `move_to_column` in bytopic.
     `test_check_action_gating…` must fail **at the bytopic `assertNotIn`**.
     This proves the view-switch readiness does not mask the gate.
   - Make `MultiRowFooter.compose` yield nothing. `test_fixture_facts` must fail
     at `_board_ready` with `keys=False`, not pass.
   - Remove the `since` witness, i.e. treat `witnessed` as always True.
     `test_readiness_stays_pending_while_the_bindings_update_is_withheld` must
     FAIL at the `task not in done` assertion. Run it once normally and once with
     `pilot.pause` wrapped to sleep 0.6s first, so its discrimination is shown to
     be independent of pace.
   - Drop the `try/except` translation around the sentinel `_until`.
     `test_readiness_rejects_a_footer_emptied…` must then FAIL on the regex
     (showing the diagnostic contract is pinned) or still pass via the
     loop-deadline route. Record which route happened.
   - Move the non-empty check before settling, as in the original plan.
     `test_readiness_rejects_a_footer_emptied…` must FAIL by returning instead
     of raising.
4. Run `bash tests/run_all_python_tests.sh --test-dir <dir holding this module>`.
   Read only the last line and check `${PIPESTATUS[0]}`.
5. Step 9 (Post-Implementation): standard cleanup, archival and commit. This is
   current-branch mode, so there is no merge.

## Risk

### Code-health risk: low
- The class-level `recompose` patch could leak beyond the test.
  `patch.object` with `addCleanup` in `setUp` and a delegating wrapper contain
  it. Test-only, single file. · severity: low · → mitigation: none
- `_until` is now copied in a second module, since t2210's copy stays in its own
  module. · severity: low · → mitigation: none

### Goal-achievement risk: low
- The original failure appeared once, in a full xdist run under foreign load. A
  loaded single-module run may not reproduce the baseline flake, so "fixed" could
  rest on mechanism reasoning alone. · severity: low (residual: addressed by
  inline post-phase measure_loaded_flake_rate, plus the deterministic step 6
  helper tests) · → mitigation: inline post-phase measure_loaded_flake_rate
- The readiness witness assumes every footer-changing deferral either queues on
  the footer's pump before the sentinel or is covered by a traced completion
  precondition: startup focus, the focus landing, and the bytopic refocus.
  Bytopic correctness also relies on `check_action(move_to_column)` reading only
  `base_filter` there. · severity: low (residual: the delayed-update test and the
  bytopic `NotIn` negative control) · → mitigation: inline post-phase measure_loaded_flake_rate

### Planned mitigations
- timing: post-phase | name: measure_loaded_flake_rate | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — unreproduced flake / unproven readiness coverage | desc: blocking loaded, interleaved 30+30 baseline-vs-fixed measurement before commit

## Final Implementation Notes
- **Actual work done:** Implemented the plan as written, in `tests/test_board_footer_multirow.py` only. Additions:
  - a verbatim copy of t2210's `_until`;
  - `_counting_recompose`, a class-level `mock.patch.object` over `MultiRowFooter.recompose` (installed in `setUp` and removed in `addCleanup`) that counts recompose starts and completions;
  - `_footer_ready` (quiet rounds via a footer-pump sentinel, plus the trigger witness, plus non-empty keys in the settled state, with a live-state `footer not ready (...)` diagnostic on every timeout route);
  - a `_FooterReadinessBase` with `_board_ready` (task cards mounted, then startup focus landed, then the footer ready) and `_focus_and_settle`;
  - the bytopic view-switch sequence (snapshot, then `_set_base_filter`, then wait for the refocus to land on a card inside a `TopicColumn`, then `_footer_ready(since=snap)`);
  - a new `FooterReadinessHelperTests` class with two tests (populated-to-empty is rejected; the helper stays pending while the bindings update is withheld, then completes once it is released).

  Six exposed tests had their single pauses replaced. `test_the_board_mounts_the_multi_row_footer` is unchanged. Every original assertion line is byte-identical.
- **Deviations from plan:** None. `self.ab.TopicColumn` exists, as the plan required. The probe found no `_test_recompose_*` or `_on_pending` names anywhere in the `MultiRowFooter` MRO.
- **Issues encountered:**
  - The loaded measurement (24 `while 1: pass` burners on a 24-core host that was already at load average ~20; 30 baseline runs interleaved with 30 fixed runs, serial pytest per module) gave **BASELINE_FAILS=0/30, FIXED_FAILS=0/30**. The before/after contrast was **not reproduced**, so none is claimed. The original failure was seen only in a full xdist run.
  - The deterministic evidence is the helper tests and the negative controls. Each control ran in a scratch detached worktree with the fixed test file copied in:
    - `move_to_column` with `show=False` fails at the original `assertIn(action, rendered)`, line 321.
    - `check_action` allowing `move_to_column` in bytopic fails at the bytopic `assertNotIn`, line 374, right after `_footer_ready(since=snap)`.
    - An empty `MultiRowFooter.compose` makes `test_fixture_facts` fail in `_board_ready` with `keys=False`.
    - Removing the witness makes the withheld test fail with "readiness returned while the update was withheld". This held at normal pace and with every `Pilot.pause` slowed by 0.6s, and the unmutated helpers pass at the slowed pace.
    - Removing the timeout translation makes the emptied test fail on its regex, because the bare `_until` message surfaces instead.
    - Checking non-empty before settling makes the emptied test fail with "AssertionError not raised".
  - The full suite (`bash tests/run_all_python_tests.sh`, xdist lane) reported `PYTHON SUITE: FAILED`. The footer module was 12/12 PASSED there. The two failures belong to other sessions' uncommitted work in the shared checkout and are unrelated to this file:
    - `test_metadata_writer_inventory` flags the untracked `.aitask-scripts/lib/relations_store.py`;
    - `test_screen_recording_cli::PickFromRuns::test_turning_point…` runs against a locally modified test file.
- **Key decisions:**
  - `_until` stays a local copy rather than being extracted to `tests/lib`, to avoid editing t2210's module.
  - The withheld-update test coordinates the producer explicitly (an `_on_pending` observer, then the release) instead of a timer. Plan review showed that timer-based controls lose their discrimination under slow pumping.
  - Bytopic correctness rests on `check_action(move_to_column)` reading only `base_filter` in that view (`aitask_board.py:2661`).
- **Upstream defects identified:** None
