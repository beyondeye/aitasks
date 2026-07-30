---
Task: t1257_board_auto_refresh_refocus_discards_scroll.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1257 — Board passive refresh discards the user's column scroll position

## Context

`ait board`'s auto-refresh timer rebuilds the whole board and then restores
focus. The restore runs through `TaskCard.on_focus` → `scroll_visible()`, so a
column the user had wheel-scrolled away from its focused card is yanked back to
that card. Same user-visible complaint t1248 fixed for the *nav-key* route,
arriving on a timer instead of a keystroke; t1248 recorded it as an upstream
defect and deferred it here.

Chain (`.aitask-scripts/board/aitask_board.py`): `_auto_refresh_tick` (:5934) →
`_refresh_board_data` (:6046) → `refresh_board` (:6151) →
`container.remove_children()` + remount → `_queue_refocus` (:6234) →
`_refocus_card` (:6221) → `card.focus()` → `TaskCard.on_focus` (:1763).

`refresh_board` unmounts and remounts every column, so the offsets are gone
structurally — the fix must carry the user's scroll position *across* the
rebuild.

> Line numbers re-derived at HEAD `f79b03549`; main advanced mid-planning
> (`1fb008967` touched this file, shifting everything ~+48 from the numbers the
> task text quotes).

### What the design experiments ruled out

A capture-then-restore scheduled after the refocus callback (the obvious fix)
was prototyped headless and **does not work**, for reasons verified in Textual
8.2.7's source:

- **One `call_after_refresh` is too early.** All callbacks posted in a cycle run
  in a single `Screen._callbacks` flush (`screen.py:1264-1282`), at which point
  the freshly mounted columns have `container_size.height == 0` and
  `max_scroll_y == 0` — so `validate_scroll_y` (`widget.py:1973`) clamps the
  restore to 0.
- **The focus scroll cannot be out-raced.** `Widget.focus()` is asynchronous
  (`app.call_later`, `widget.py:4588-4597`), and `scroll_visible` *ignores*
  `immediate=True` for a widget with no size yet — it re-posts itself through
  `parent.call_after_refresh` (`widget.py:3764-3777`). A rebuilt card is always
  in that state, so t1248's "synchronous and unanimated" contract silently
  degrades to a deferred scroll landing in a later flush. Two further pulls
  exist: `Screen.set_focus` schedules `scroll_to_center` (`screen.py:1138-1145`),
  and tearing down the focused widget makes Textual re-home focus onto a card of
  its own choosing, queueing yet another deferred scroll. The number of pending
  scrolls after a rebuild is data-dependent — no fixed number of hops wins, and
  `focus(scroll_visible=False)` alone measurably does not either.
- **`_recompose_column` is not the cheap way out** the task hoped for:
  `Widget._scroll_update` re-clamps `scroll_y` on every virtual-size change
  (`widget.py:4145`), so the transient zero-children state zeroes it there too.

## Approach — refuse scrolls for the duration of a passive refresh

Make the scroll *refusable* rather than out-raced. `allow_vertical_scroll` is
Textual's documented override seam ("*May be overridden if you want different
logic regarding allowing scrolling*", `widget.py:575-583`) and is honoured by
**every** scroll path — `_scroll_to` (`widget.py:2752-2753`) and
`scroll_to_region` (`widget.py:3693-3697`) — each with `force=True` as the
deliberate bypass. One seam therefore covers `on_focus`'s scroll, its deferred
variant, `scroll_to_center`, and the uninvited re-home focus.

So: hold a board-wide scroll lock across the rebuild, then re-apply the captured
offsets with `force=True` once the columns can actually hold them.
`TaskCard.on_focus`, `_refocus_card`, `_queue_refocus` and `refresh_board` are
**not touched** — which is what keeps AC 2 / Case 8 safe.

Scoped to the *passive* refreshes (auto-refresh tick — both branches — and `r`).
Card moves, edits and dialogs (~30 `refresh_board` call sites) keep today's
follow-the-card behaviour.

Four properties are load-bearing and are designed in explicitly:

- **The lock's fail-safe is armed at acquisition, not inside the restore.**
  `Screen._invoke_and_clear_callbacks` (`screen.py:1264-1272`) has **no**
  per-callback `try` — unlike `MessagePump._flush_next_callbacks`
  (`message_pump.py:695-706`), which does. So an exception in an *earlier*
  callback of the batch (e.g. `apply_filter`) drops every remaining callback,
  and a restore-internal `try/finally` or timer would never run at all: the lock
  would stick and the board would stop scrolling. The release timer is therefore
  armed on the same line that sets the lock.
- **Every deferred continuation carries a generation token.** A second `r` (or a
  sync completion) landing inside the first restore window must own the state
  alone; stale callbacks and stale timers from the superseded refresh must not
  restore offsets onto — or unlock — the newer rebuild.
- **Readiness is a scroll-*range* condition, not a size condition.** `force=True`
  bypasses `allow_vertical_scroll`, **not** `validate_scroll_y`'s clamp, so
  restoring before `max_scroll_y` is computed silently yields 0. The retry
  predicate is "this column cannot yet hold its captured offset", with the
  bounded budget deliberately falling through to an intentional clamp when the
  refreshed content genuinely shrank.
- **The timeout *retires* the generation; it does not merely unlock.** Unlocking
  alone would leave `gen` current and the snapshot pending, so (a) a late
  `_restore_column_scroll` would pass its own guard and force the stale offset
  over scrolling the user did *after* the timeout, and (b) the next refresh would
  reuse the stale snapshot, because its capture is skipped while
  `_pending_scroll_offsets` is non-`None`. The fail-safe therefore bumps the
  generation (making every in-flight continuation inert) and clears the snapshot
  (so the next refresh captures fresh state).

## Changes — `.aitask-scripts/board/aitask_board.py`

**1. Scroll-lock mixin on the four column classes** (`InFlightColumn` :1835,
`TopicColumn` :1877, `TrailColumn` :2051, `KanbanColumn` :2446 — all bare
`VerticalScroll` subclasses), declared as
`class KanbanColumn(_ScrollLockMixin, VerticalScroll)` so `super()` resolves
through the MRO:

```python
class _ScrollLockMixin:
    """Refuse scrolls while the app is rebuilding the board (t1257).

    `allow_vertical_scroll` is Textual's sanctioned refusal seam: every scroll
    path checks it and every path takes `force=True` as the bypass, so this one
    override covers the focus-driven scroll, its deferred variant for an
    unlaid-out card, `Screen.set_focus`'s `scroll_to_center`, and the focus
    Textual re-homes by itself when the focused widget is torn down.
    """

    @property
    def allow_vertical_scroll(self) -> bool:
        try:
            app = self.app
        except RuntimeError:      # NoActiveAppError, raised during teardown
            return super().allow_vertical_scroll
        if getattr(app, "_board_scroll_lock", False):
            return False
        return super().allow_vertical_scroll
```

**2. `KanbanApp` class attributes** (near :5334 — class-level, so no `__init__`
edit and the defaults are safe before mount):

```python
_board_scroll_lock = False
_pending_scroll_offsets = None
_scroll_restore_gen = 0
_scroll_lock_timer = None
_SCROLL_RESTORE_MAX_ATTEMPTS = 8    # frames; bounded by construction
_SCROLL_LOCK_TIMEOUT = 1.0          # seconds; fail-safe, see _refresh_board_preserving_scroll
```

**3. One shared entry point for the passive refresh** (next to
`_refresh_board_data`):

```python
def _refresh_board_preserving_scroll(self, refocus_filename: str = "",
                                     refresh_locks: bool = True):
    """Rebuild the board without discarding the user's scroll position."""
    gen = self._scroll_restore_gen = self._scroll_restore_gen + 1
    if self._pending_scroll_offsets is None:
        # A refresh landing mid-restore reuses the first snapshot: re-capturing
        # would record the transient zeros of a half-laid-out rebuild.
        self._pending_scroll_offsets = {
            col.col_id: col.scroll_y for col in self._column_widgets()}
    self._board_scroll_lock = True
    # Fail-safe armed HERE, on the acquisition line. Screen's callback flush
    # (screen.py:1264-1272) has no per-callback try, so an exception in an
    # earlier callback drops the whole batch — including the restore below.
    # A release scheduled inside the restore would never fire, leaving the
    # board permanently un-scrollable.
    self._scroll_lock_timer = self.set_timer(
        self._SCROLL_LOCK_TIMEOUT, lambda: self._abandon_scroll_restore(gen))
    self.refresh_board(refocus_filename=refocus_filename,
                       refresh_locks=refresh_locks)
    self.call_after_refresh(self._restore_column_scroll, gen, 0)

def _restore_column_scroll(self, gen: int, attempt: int = 0):
    """Re-apply the captured offsets once the columns can hold them."""
    if gen != self._scroll_restore_gen:
        return                      # superseded; the newer refresh owns the state
    cols = self._column_widgets()
    offsets = self._pending_scroll_offsets or {}
    # Readiness is a RANGE condition. force=True bypasses allow_vertical_scroll,
    # not validate_scroll_y's clamp to max_scroll_y (widget.py:1973) — and
    # max_scroll_y derives from virtual_size, which lands after container_size.
    # Falling through the budget restores what fits, which is the correct
    # outcome when the refreshed content genuinely shrank.
    if attempt < self._SCROLL_RESTORE_MAX_ATTEMPTS and any(
            offsets.get(col.col_id, 0) > col.max_scroll_y for col in cols):
        self.call_after_refresh(self._restore_column_scroll, gen, attempt + 1)
        return
    try:
        for col in cols:
            if col.col_id in offsets:
                col.scroll_to(y=offsets[col.col_id], animate=False,
                              immediate=True, force=True)
    finally:
        self._pending_scroll_offsets = None
        if self._scroll_lock_timer is not None:
            self._scroll_lock_timer.stop()     # the fail-safe is no longer needed
            self._scroll_lock_timer = None
        # One extra flush before unlocking, so focus scrolls deferred by the
        # rebuild are still refused; the acquisition timer is the real backstop.
        self.call_after_refresh(self._release_board_scroll_lock, gen)

def _release_board_scroll_lock(self, gen: int):
    if gen != self._scroll_restore_gen:
        return                      # an older refresh must not unlock a newer one
    self._board_scroll_lock = False

def _abandon_scroll_restore(self, gen: int):
    """Timeout fail-safe: retire `gen` and drop its snapshot.

    Unlocking alone is not enough. `gen` would stay current, so a restore
    callback arriving after the timeout would force the captured offset over
    whatever the user scrolled in the meantime, and the still-pending snapshot
    would be adopted by the *next* refresh (whose capture is skipped while
    `_pending_scroll_offsets` is set). Bumping the generation makes every
    in-flight continuation for `gen` inert; clearing the snapshot makes the next
    refresh capture fresh state.
    """
    if gen != self._scroll_restore_gen:
        return                      # a newer refresh already owns the state
    self._scroll_restore_gen += 1
    self._pending_scroll_offsets = None
    self._scroll_lock_timer = None
    self._board_scroll_lock = False
```

`_scroll_lock_timer` is a single slot: an overlapping refresh overwrites the
handle without stopping the older timer, which then fires and no-ops on the
generation guard. Harmless by construction — the guard, not the handle, is what
makes a stale fail-safe inert.

`scroll_to(..., animate=False)` rather than assigning `scroll_y` directly:
`_scroll_to` sets `scroll_target_y = scroll_y = y` (`widget.py:2947-2949`),
preserving t1248's invariant that the wheel handler's `scroll_target_y` never
diverges from `scroll_y`.

`_column_widgets()` (:6733) is the canonical column-class union, so no new class
list is introduced. During the first post-refresh callback it briefly returns
both old and new columns (`remove_children()` is asynchronous, `mount` is not);
writing an offset onto a doomed widget is harmless, so no dedupe is needed — the
only ordering rule is that the *capture* happens before the teardown.

**4. Route the two passive call sites through it:**

- `_refresh_board_data` (:6046) keeps its `focused.task_data.filename` read,
  `load_tasks()` and `_auto_expand_locked()` lines; its `refresh_board(...)`
  call (:6056) becomes
  `self._refresh_board_preserving_scroll(refocus_filename=refocus, refresh_locks=True)`.
  Serves the auto-refresh tick's non-sync branch **and** the `r` key.
- `_run_sync` (:7848, `@work(exclusive=True, thread=True)`) has **four** callers,
  and only one of them is passive: the tick at :5942. The others —
  `action_sync` (:7845), `action_trail_sync` `S` (:6149) and the post-rename sync
  (:9131) — are user-initiated and outside this task's scope, so the behaviour is
  opted into per call rather than swapped wholesale:

  ```python
  @work(exclusive=True, thread=True)
  def _run_sync(self, show_notification: bool = True, show_overlay: bool = False,
                preserve_scroll: bool = False):
      ...
      # (:7887) passive auto-refresh keeps the user's scroll; a user-initiated
      # sync keeps today's follow-the-focused-card behaviour.
      if preserve_scroll:
          self.app.call_from_thread(self._refresh_board_preserving_scroll,
                                    refresh_locks=True)
      else:
          self.app.call_from_thread(self.refresh_board, refresh_locks=True)
  ```

  `_auto_refresh_tick` (:5942) becomes
  `self._run_sync(show_notification=False, preserve_scroll=True)`. One marshalled
  call either way, so the capture runs on the main thread with the DOM intact.

**Declared exclusions** (deliberate, not oversights):

- User-initiated sync (`s`, `S`, post-rename) keeps today's behaviour — the
  scroll follows the focused card. Extending preservation there is a separate
  UX decision, not part of "passive refresh + `r`".
- `_run_sync` passes no `refocus_filename` today, so focus lands on the column's
  first card. That focus quirk is pre-existing and left alone; only the scroll is
  preserved.
- `_rerender_trail` (:6065), the By-Trail `r` twin, has the same class of bug but
  is not reachable from the auto-refresh tick. Out of scope.

## Test — new `tests/test_board_auto_refresh_scroll.py`

Harness copied from the t1248 suite (`tests/test_board_scroll_focus_jump.py`):
`unittest.TestCase`, `os.chdir(REPO_ROOT)` + `sys.path` bootstrap in
`setUpClass` (the runner scrubs `PYTHONPATH`, t1236), `asyncio.run`, the
synthetic `Tall(30) | Side(10)` layout, and the `_wheel` / `_settle` /
`_scrolled_away` / `_column` / `_cards` helpers. As in Case 11 of
`test_board_empty_column_focus.py:323`, stub `mgr.load_tasks` — and
`refresh_git_status` / `refresh_lock_map`, which shell out with 5s/10s timeouts —
so the tick can neither repopulate the synthetic layout from disk nor stall.

**Behaviour (AC 1 / AC 2)**

1. **`test_auto_refresh_tick_preserves_wheel_scroll`** — wheel TALL away from the
   focused card, `app._auto_refresh_tick()` (with `sync_on_refresh` off), settle;
   assert both `scroll_y` and `scroll_target_y` equal the pre-tick values.
   *Fails on current code.*
2. **`test_r_key_refresh_preserves_wheel_scroll`** — same via
   `app.action_refresh_board()`.
3. **`test_refresh_still_restores_focus`** — `app.screen.focused` is the card for
   the pre-tick filename; `app._get_focused_col_id() == TALL` (AC 2).
4. **`test_vanished_focused_card_falls_back_to_its_column`** — drop the focused
   card from `mgr.task_datas` before the tick: focus falls back to the column
   (`_refocus_card` → `_refocus_column`) *and* the other column's offset
   survives. Pins the AC 2 / Case 8 interaction.
5. **`test_unfocused_column_scroll_survives_the_tick`** — scroll SIDE while focus
   stays in TALL.

**Lock fail-safe (concern 1)**

6. **`test_lock_released_when_the_restore_never_runs`** — with
   `_SCROLL_LOCK_TIMEOUT` patched to `0.05` and `_restore_column_scroll` patched
   to a no-op (simulating exactly the dropped-batch failure: the callback never
   fires — no exception is raised, which would otherwise abort the Pilot app),
   assert after the timeout that `app._board_scroll_lock` is falsy *and* a
   subsequent `_wheel` still moves the column. This test fails if the timer is
   armed inside the restore instead of at acquisition.
7. **`test_lock_released_on_the_normal_path`** — plain tick: lock falsy after
   settle, wheel still works.
7b. **`test_timeout_retires_the_generation`** — same no-op-restore setup; after
   the timeout assert `_pending_scroll_offsets is None` and that
   `_scroll_restore_gen` advanced past the abandoned generation. Then wheel to a
   *new* position and invoke the abandoned generation's continuation directly
   (`app._restore_column_scroll(abandoned_gen)`): the new position must survive
   — pins that a late callback cannot overwrite post-timeout user input.
7c. **`test_next_refresh_captures_fresh_state_after_a_timeout`** — after the
   abandoned refresh above, wheel to a new offset and run a normal tick; the
   restored offset must be the *new* one, proving the stale snapshot was dropped
   rather than adopted.

**Generation ownership (concern 2)**

8. **`test_overlapping_refresh_restores_the_users_offset_once`** — issue a second
   `_refresh_board_preserving_scroll` before the first restore window drains;
   after settle assert the offsets equal the *original* user positions (not the
   transient zeros), `_pending_scroll_offsets is None`, the lock is released, and
   `_scroll_restore_gen` advanced by exactly 2.
9. **`test_stale_generation_callback_is_inert`** — call
   `app._restore_column_scroll(gen - 1)` and
   `app._release_board_scroll_lock(gen - 1)` directly while a newer generation
   holds the lock; assert neither touched the offsets nor cleared the lock.

**Restore readiness (concern 3)**

10. **`test_restore_survives_a_delayed_layout`** — patch `max_scroll_y` on the
    column class to report `0` until `_restore_column_scroll` has retried twice
    (a counter flipped by a wrapper around the real method, so the delay is
    deterministic rather than timing-based), then delegate to the real property.
    Assert the captured offset is still restored — i.e. the retry loop, not luck,
    is what lands it.
11. **`test_restore_is_bounded_when_layout_never_settles`** — same patch, never
    unblocking: assert the loop stops at `_SCROLL_RESTORE_MAX_ATTEMPTS`, the lock
    is released, and the board scrolls again (bounded degradation, not a hang).
12. **`test_shrunken_content_clamps_intentionally`** — remove most TALL tasks
    before the tick; assert the restore clamps to the new `max_scroll_y` rather
    than retrying to exhaustion or restoring an impossible offset.

**Sync route (concern 4)**

13. **`test_auto_refresh_sync_branch_preserves_scroll`** — drive the **production
    route**, not the helper: set `mgr.settings["sync_on_refresh"] = True`, patch
    `aitask_board.DATA_WORKTREE` to an existing path and
    `aitask_board.run_sync_batch` to return a `STATUS_NOTHING` result, wrap
    `app.call_from_thread` with a recorder, then call `app._auto_refresh_tick()`
    and `await app.workers.wait_for_complete()` (`_run_sync` is
    `@work(exclusive=True, thread=True)`). Assert the recorded dispatch targets
    include `_refresh_board_preserving_scroll` and **not** `refresh_board`, and
    that the wheel offset survived. Fails if :7887 keeps calling `refresh_board`
    or if the tick omits `preserve_scroll=True`.
14. **`test_user_initiated_sync_keeps_follow_the_card`** — scope pin for the new
    parameter's default: same stubs, but call `app._run_sync(show_notification=False)`
    (as `action_sync` does); the recorded dispatch target must be `refresh_board`.

The tick is invoked directly rather than waited on: `test_board_bytrail_view.py:678`
already pins `_auto_refresh_tick` → `_refresh_board_data`, and a real 60s timer
is untestable in a Pilot run.

## Verification

`pytest` is not installed in the ait venv, so the runner takes the
`unittest discover` backend.

```bash
PY=/home/ddt/.aitask/venv/bin/python          # = require_ait_python

# Fast dev loop on the new file alone:
PYTHONPATH= "$PY" -m unittest discover -s tests \
    -p 'test_board_auto_refresh_scroll.py' -v

# Board regression surface (AC 2):
PYTHONPATH= "$PY" -m unittest discover -s tests -p 'test_board_*.py' -v

# Framework verdict (read ONLY the last line —
# `PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`, on stderr; piping discards
# the exit status, so use ${PIPESTATUS[0]}):
bash tests/run_all_python_tests.sh
```

**Baseline failure proof** — no `git stash`/`git checkout` (another session has
uncommitted work in this checkout): keep the patched board at
`/tmp/.../aitask_board.fixed.py`, restore the pristine one with
`git show HEAD:.aitask-scripts/board/aitask_board.py > .aitask-scripts/board/aitask_board.py`,
run the new file, then copy the fixed version back. Expected on pristine code:
cases 1, 2, 5, 10, 12, 13 fail (and 6/7b/7c/8/9/11/14 error on the missing
attributes, which is itself the discriminator). `find tests .aitask-scripts -name
__pycache__ -prune -exec rm -rf {} +` between the two runs so no stale bytecode
masks the flip.

Manual smoke (real terminal): set `auto_refresh_minutes: 1` in
`aitasks/metadata/board_config.json`, run `ait board`, wheel a column away from
the focused card, wait for the tick — the column must stay put, and the board
must still scroll afterwards.

Step 9 (Post-Implementation) applies as usual: no separate branch (profile
`fast` works on the current branch), then archival.

## Risk

### Code-health risk: medium
- A **stuck lock leaves the board un-scrollable** — the one serious failure mode.
  Root cause is real: `Screen._invoke_and_clear_callbacks` (`screen.py:1264-1272`)
  has no per-callback `try`, so an exception in an earlier callback drops the
  restore entirely. Countered by arming the fail-safe *at acquisition*, having it
  **retire** the generation and snapshot (not merely unlock), generation-guarding
  it so it cannot touch a newer refresh, and self-healing on the next refresh;
  pinned by tests 6/7/7b/7c/9 · severity: medium · → mitigation: guards are in
  this plan, not deferred
- The lock window makes scroll state briefly authority-owned rather than
  input-owned, so a *late* continuation could write a stale offset over fresh
  user input. Closed by the retirement semantics above (late callbacks are inert),
  pinned by test 7b · severity: low · → mitigation: TBD
- Overriding `allow_vertical_scroll` on four column classes changes a
  framework-level permission for those widgets. Scope is one file and the
  behaviour is inert whenever the lock is false · severity: low · → mitigation: TBD
- Wheel input over a column is refused for the restore window (≤ 8 frames, hard
  bound `_SCROLL_RESTORE_MAX_ATTEMPTS`, absolute bound `_SCROLL_LOCK_TIMEOUT`)
  and is dropped — it bubbles to `#board_container`, a `HorizontalScroll`, which
  refuses vertical. On a timer that fires every N minutes · severity: low ·
  → mitigation: TBD

### Goal-achievement risk: low
- A passive refresh no longer brings the focused card back into view: if you had
  scrolled away, the cursor stays off-screen. That *is* AC 1, and it matches the
  model t1248 established — the next nav key re-anchors the cursor via
  `_reanchor_to_viewport` (:6809) · severity: low · → mitigation: TBD

Mitigation follow-up tasks were offered and declined (the guards above live in
this plan rather than in deferred tasks).
