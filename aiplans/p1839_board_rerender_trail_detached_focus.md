---
Task: t1839_board_rerender_trail_detached_focus.md
Base branch: main
Output branch: main
---

# t1839 — Board: never leave keyboard focus on a detached card after a By-Trail re-render

## Context

t1794_6 found that `TrailsApp`, under load, could end up with `screen.focused`
pointing at a `TrailGhostCard` that had been **removed from the DOM**. A
detached widget's binding chain no longer reaches the App, so every key is dead
until something else takes focus. `TrailsApp` fixed its own side
(`_focused_card` requires `is_attached`, plus a bounded re-queuing rescue). The
board shares the re-render path (`TrailScreenMixin._rerender_trail`,
`.aitask-scripts/board/board_trail_screen.py:399`), but its
`KanbanApp._focused_card` (`aitask_board.py:6473`) is a bare `screen.focused`
read, and the board has **no rescue** at all.

### What pre-plan probing established (scratchpad Pilot probe, fixture board, `_ghost_doc`)

- **The task's hypothesis does not hold on the board.** After
  `_on_trail_drift → _rerender_trail`, the re-mounted cards can be queried on
  the very first hop (`cards=2` at hop 0), because `mount()` inserts into the
  DOM synchronously. Textual resets focus to the board container at hop 0, and
  the queued `_refocus_card` lands on the new card at hop 1. `v` stays active.
- The result is the same when a deferred `card.focus()` is queued just before or
  just after the re-render. The organic bad state was **not reproduced on the
  board**.
- **The only mechanism that can produce the dead state** (Textual 8.2.7 source):
  `Widget.focus()` is deferred (`app.call_later(set_focus)`), and
  `Screen.set_focus` does not check `_pruning`. `App._prune` resets focus only
  once, when pruning *starts*. So if a stale `set_focus` for a card that is
  being removed lands **after** the refocus has run, the removed card keeps
  focus and nothing resets it again. t1794_6's own test built this state
  artificially ("remove, then `set_focus` back"), and this plan does the same.

So this is a **defensive hardening**. It gives the board the recovery TrailsApp
already has. It does not fix an observed board failure.

## Approach (board-only; the mixin, `TrailsApp` and all non-trail refreshes are untouched)

The watch hangs off a **`KanbanApp._rerender_trail` override**, *not* the shared
`_queue_refocus`. Review of the first draft found two problems with putting it
in `_queue_refocus`:

- **Scope.** The board calls `_queue_refocus` from 7 places: `refresh_board`
  (normal, In-Flight, By-Topic) and the per-column recompose and transplant
  paths (`aitask_board.py:5602, 5612, 5618, 5648, 5735, 5744, 5770`). A rescue
  there would silently change focus restoration in views that have no contract
  or test for it.
- **Cost.** On a healthy refresh, a re-queue-until-hops-run-out loop schedules
  6 callbacks per call, auto-refresh included.

`KanbanApp` comes before `TrailScreenMixin` in the MRO (`aitask_board.py:4680`).
Every mixin call site (`board_trail_screen.py:456, 704, 783, 814, 1039`) calls
`self._rerender_trail`, so the override covers every By-Trail re-render and
nothing else. `TrailsApp` (`trails_app.py:77`) keeps its own rescue.

The bounded re-queue that `TrailsApp` uses to wait for cards is **not** copied.
On the board the cards can be queried at hop 0 (see the probe above).

## Implementation steps

1. **`_focused_card` / `_focused_unit` treat a detached widget as "nothing
   focused"** (`.aitask-scripts/board/aitask_board.py:6473` and the
   `_focused_unit` immediately below it). Add `and focused.is_attached` to each
   isinstance check. Extend each docstring with one sentence: a card that a
   re-render removed still sits in `screen.focused` and must not count.
   `is_attached` is a parent-pointer walk, not a DOM query, so the t1243_7
   hot-path measurement (zero whole-board walks) still holds.
   `_get_focused_col_id` goes through `_focused_unit`, so it inherits the
   change. These two helpers are the only change visible to other views, and
   they move no focus. They only stop gates and helpers from treating a dead
   widget as a live selection. A healthy board never has a detached
   `screen.focused`, so other views behave exactly as before.

2. **`KanbanApp._rerender_trail` override plus a generation-scoped watch**
   (`aitask_board.py`, placed next to `_queue_refocus`):
   ```python
   #: Hops the post-re-render detached-focus watch stays armed (t1839).
   _DETACHED_FOCUS_HOPS = 5

   def _rerender_trail(self, refocus_filename: str = ""):
       """Board wrapper: the shared re-render, then a bounded watch for a
       detached focus (t1839). ..."""
       if self.base_filter != "bytrail":
           return super()._rerender_trail(refocus_filename)
       refocus_col_id = self._get_focused_col_id() or ""
       super()._rerender_trail(refocus_filename)
       self._detached_focus_gen += 1
       self.call_after_refresh(self._watch_detached_focus,
                               self._detached_focus_gen, refocus_filename,
                               refocus_col_id, self._DETACHED_FOCUS_HOPS)

   def _watch_detached_focus(self, gen, filename, col_id, hops):
       # Superseded by a newer re-render, or the view changed: stop.
       if gen != self._detached_focus_gen or self.base_filter != "bytrail":
           return
       if self._modal_is_active():
           return
       focused = self.screen.focused if self.screen else None
       if focused is not None and not focused.is_attached:
           self._restore_trail_focus(filename, col_id)
           return
       if hops > 0:
           self.call_after_refresh(self._watch_detached_focus,
                                   gen, filename, col_id, hops - 1)
   ```
   `_detached_focus_gen = 0` is set in `__init__` next to the other trail
   state.

   **Restore contract (`_restore_trail_focus`).** The rescue restores **what
   this re-render was restoring**, not the leftmost card. The order is decided
   up front, because `.focus()` is deferred and a synchronous re-read cannot
   tell whether it worked:
   1. If an attached, visible card for `filename` exists (`query(TaskCard)`),
      call `_refocus_card(filename, col_id)` (`aitask_board.py:5650`).
   2. Otherwise, if `col_id` has a `_column_focus_target`, call
      `_refocus_column(col_id)`.
   3. Otherwise use `_first_board_focus_target()` (`aitask_board.py:6427`),
      and if that is `None`, `screen.set_focus(None)`. This is the same order
      `_claim_startup_focus` uses.

   **Cost contract:** at most one live watch chain. A newer re-render bumps the
   generation, so any older chain stops at its next hop. One chain makes at most
   `_DETACHED_FOCUS_HOPS + 1` callbacks. Each callback is two attribute compares
   plus one `is_attached` parent walk: no query, and no work outside By-Trail.
   `refresh_board` and the per-column paths schedule nothing new.

3. **Tests: new class `DetachedFocusRescueTests(ByTrailTestBase)` in
   `tests/test_board_bytrail_view.py`** (idiom of
   `test_ghost_navigation_and_detail`: `_enter_synthetic_bytrail`,
   `_ghost_doc()`, `self._run(go())`):
   - `test_focused_card_ignores_a_detached_card`: build the precondition as
     t1794_6 did (`await card.remove()`, `app.screen.set_focus(card)`). Assert
     that `screen.focused is card` and it is not attached, and that
     `_focused_card()`, `_focused_unit()` and `_get_focused_col_id()` all
     return `None`.
   - `test_drift_rerender_rescues_a_late_stale_focus_to_the_same_card`: focus
     card A, note its filename, and grab a different old card `dead`. Call the
     real `app._on_trail_drift(app._trail_gen, "art:trail-test", "CURRENT",
     [])`, then schedule the stale focus to land after the refocus
     (`app.call_after_refresh(lambda: app.call_after_refresh(lambda:
     app.screen.set_focus(dead)))`). After about 8 pauses, assert that focus is
     an attached `TaskCard` **whose filename is A's**, which pins the restore
     contract (same card, not leftmost), and that `"v" in
     app.screen.active_bindings`. **Negative control in the same test:** repeat
     with `_watch_detached_focus` patched to a no-op, and assert that focus is
     `dead` and detached. This proves the precondition is real. If the control
     does not reach the dead state, the test fails and does not pass trivially.
   - `test_restore_falls_back_when_the_card_is_gone`: same late stale focus,
     but the refocus filename names a card that the re-render no longer
     produces (drop that entry from the doc before `_on_trail_drift`). Assert
     that focus lands on an attached target in the captured column when the
     column survives, or otherwise on `_first_board_focus_target()`.
   - `test_watch_is_scoped_and_bounded`: wrap `_watch_detached_focus` in a
     counting spy.
     (a) Leave By-Trail (`_set_base_filter("all")`), call `refresh_board()`
     and a per-column refresh, then pause 8 times. The spy count is **0**:
     other views are untouched.
     (b) In By-Trail, call `_rerender_trail()` 10 times back to back, then
     pause 10 times. The count is at most `10 + _DETACHED_FOCUS_HOPS + 1`,
     because superseded chains stop after one hop. This measures the cost
     contract instead of asserting it in prose.

### Post-phase (risk mitigations)

1. [stress_bytrail_focus_probe] After steps 1–3 are green, write a scratchpad
   Pilot probe (not committed) based on `ByTrailTestBase`. It runs about 200
   iterations on the `_ghost_doc()` By-Trail board. Each iteration randomly
   interleaves `pilot.press("left"/"right")`, a deferred `card.focus()` on an
   arbitrary current card, and a real
   `app._on_trail_drift(app._trail_gen, "art:trail-test", "CURRENT", [])`,
   with 0 to 2 pauses between steps. After each iteration it settles for 8
   pauses and records whether `screen.focused` is detached. Run the probe
   twice while `bash tests/run_all_python_tests.sh` loads the machine: once
   as-is, and once with `_watch_detached_focus` stubbed to a no-op. Record both
   counts and any sequence that produced a detached focus in the plan's Final
   Implementation Notes. If the stubbed run finds an organic trigger, add that
   sequence as a further committed test in `DetachedFocusRescueTests`.

## Verification

- `~/.aitask/venv/bin/python -m pytest tests/test_board_bytrail_view.py -q`: the
  new class passes, and so does everything else in the file.
- Keymap characterization: `tests/test_board_keymap_characterization.py` stays
  green (required by the task).
- Hot-path and focus neighbours: `tests/test_board_movement.py` (attribution
  benchmark), `tests/test_board_move_command.py`,
  `tests/test_board_footer_visibility.py` and `tests/test_trails_app.py`.
- Full suite: `bash tests/run_all_python_tests.sh`. Read the final
  `PYTHON SUITE:` line and check the exit status without a pipe.
- Mutant checks: (a) remove the `is_attached` clause from `_focused_card`;
  (b) stub `_watch_detached_focus`; (c) drop the generation check. Each must
  turn its matching new test red. Run the mutants on a scratch copy of the
  module, never through git restore in the shared tree.

## Step 9 (Post-Implementation)

Current-branch mode: commit the code (`bug: … (t1839)`), then archive via the
standard Step 9 flow.

## Risk

### Code-health risk: low
- `_focused_card` / `_focused_unit` sit on the measured `check_action` hot path.
  `is_attached` adds a parent walk of about 10 nodes per call, not a query. The
  attribution benchmark in `test_board_movement.py` is the guard ·
  severity: low · → mitigation: none
- The watch adds queued callbacks after By-Trail re-renders only (one live
  chain, at most 6 callbacks, superseded chains stop at their next hop). This
  is measured by `test_watch_is_scoped_and_bounded`. Every other refresh path
  is unchanged · severity: low · → mitigation: none
- An override on `KanbanApp` of a mixin method adds a second place to read when
  changing `_rerender_trail`. The override's docstring names the mixin method
  and t1839 · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The organic trigger was not reproduced on the board. The fix and its test
  target the one mechanism the Textual source allows (a late `set_focus` on a
  pruning card), and they construct that state by hand. If the real trigger is
  a different path, a detached focus that arrives more than about 6 hops after
  a re-render would still go unrescued · severity: medium (residual — probed,
  not proven, by inline post-phase stress_bytrail_focus_probe) · → mitigation:
  inline post-phase stress_bytrail_focus_probe

### Planned mitigations
- timing: post-phase | name: stress_bytrail_focus_probe | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: organic trigger not reproduced on the board | desc: Loaded, randomized drift-re-render + focus-churn Pilot probe, with/without the rescue; findings recorded, organic sequence promoted to a test if found

## Final Implementation Notes

- **Actual work done:** Steps 1–3 as planned, all in
  `.aitask-scripts/board/aitask_board.py` + `tests/test_board_bytrail_view.py`:
  - `_focused_card` / `_focused_unit` require `is_attached`.
  - `KanbanApp._rerender_trail` override (By-Trail only; delegates to the mixin
    otherwise) arms `_watch_detached_focus` — generation-scoped via
    `_detached_focus_gen` (initialised in `__init__` after `_init_trail_state()`),
    bounded by `_DETACHED_FOCUS_HOPS = 5`.
  - `_restore_trail_focus`: same card → captured column → `_first_board_focus_target()`
    → `set_focus(None)`, decided up front.
  - `DetachedFocusRescueTests` (4 tests).
- **Deviations from plan:** test fixtures tightened during implementation so each
  restore rung is discriminated: the same-card test focuses B with A (the
  leftmost target) as the dead card, and `_three_ghost_doc` adds the extra member
  to **wave 2** so "column fallback" (→ B in `trail-w2`) differs from "leftmost"
  (→ A). Before that change the "restore always leftmost" mutant passed both tests.
- **Mutants (scratch runner patching the fixture-loaded module, tree untouched):**
  unchecked `_focused_card` → red test 1; watch no-op → red tests 2, 3, 4; no
  generation check → red test 4; restore-always-leftmost → red tests 2, 3.
- **Post-phase [stress_bytrail_focus_probe]:** 200 randomized iterations
  (arrow keys, deferred `card.focus()` on arbitrary cards, real drift re-renders,
  0–2 pauses) run concurrently with the full Python suite (load avg 6–8):
  **0/200 detached with the watch, 0/200 with the watch stubbed.** No organic
  board trigger found, consistent with the pre-plan probe; nothing promoted to a
  committed test. The goal-achievement residual (fix targets a constructed
  precondition) stands as recorded in `## Risk`.
- **Issues encountered:** none beyond the fixture discrimination above.
- **Upstream defects identified:** None
- **Key decisions:** watch scoped to By-Trail re-renders via an override rather
  than the shared `_queue_refocus` (review feedback: 7 other callers, and
  per-refresh callback cost); no TrailsApp-style wait-for-mount re-queue, since
  board cards are queryable at hop 0.

## Post-Review Changes

### Change Request 1 (2026-09-18 16:20)
- **Requested by user:** `_watch_detached_focus` returned permanently on
  `_modal_is_active()`, but `_on_trail_drift` (board_trail_screen.py:771) re-renders
  under a By-Trail modal; the stale focus lands on the underlying BoardScreen, so
  the watch could end before the dead state arose and dismissing the modal exposed
  dead keys. Confirmed valid — and additionally, under a modal `self.screen` IS the
  modal, so the watch was reading the wrong screen's focus, and the caller's
  refocus target (read via `_focused_card` → `self.screen`) was empty.
- **Changes made:**
  - `_board_screen()` (bottom of `screen_stack`); the watch reads the board
    screen's focus and keeps running while a modal is up.
  - Detached focus found under a modal → `board.set_focus(None)` immediately (the
    dead reference never survives to dismissal) and the restore is parked in
    `_detached_focus_pending` (gen, filename, col_id).
  - New `BoardScreen.on_screen_resume` → `KanbanApp._resume_detached_focus()`:
    applies the parked restore unless superseded (gen), the view changed, a modal
    is still up, or the board already holds a live focus.
  - The override takes the watch's restore target from the board screen when a
    modal is active (the caller's modal-read target is empty).
  - Test `test_rescue_survives_a_modal_open_over_the_rerender` (TrailSummaryScreen
    via `v`, drift + late stale focus on the board screen, with negative control).
  - Mutants: old return-on-modal, watch-reads-self.screen, resume-hook no-op,
    no-board-screen-target → each red on the new test (8/8 mutants red overall).
  - Neighbours 313 passed / 2 skipped; full suite PASSED.
- **Files affected:** .aitask-scripts/board/aitask_board.py, tests/test_board_bytrail_view.py
