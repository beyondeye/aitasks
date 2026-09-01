---
Task: t1653_minimonitor_bottom_pin_lost_on_refresh.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1653 — minimonitor: bottom-of-list scroll pin lost on refresh

## Context

`ait minimonitor` rebuilds its whole agent list on every status tick
(`_rebuild_pane_list` → `remove_children()` + `mount_all()`). While the container
is childless `max_scroll_y` is 0, so Textual's `validate_scroll_y` clamps
`scroll_y` to 0 — every tick. Since t1539 the only thing holding the user's
position is `_restore_list_scroll`, called once per tick from
`call_after_refresh`.

For a user parked at the **bottom** of the list that restore is wrong, and the
error compounds. `_capture_list_scroll` records
`at_bottom = max_y <= 0 or scroll_y >= max_y - 1` from **pre-rebuild** geometry
and `_restore_list_scroll` applies it once **after** the rebuild via
`scroll_end(immediate=True)`. Both halves are stale by construction:

* the measured trace shows `max_scroll_y` swinging 67 → 73 → 88 *within* a tick
  as cards mount and card heights churn, so a restore that fires against a
  non-final range is silently clamped and nothing re-scrolls when the range
  settles;
* once the position has drifted more than one row, `at_bottom` reads False, the
  mid-list anchor branch takes over and faithfully freezes the *wrong* position;
* the bottom branch has no range gate at all — `minimonitor_app.py:404-409`
  concedes the `target > max_scroll_y` retry is "vacuously false" when the
  target *is* `max_scroll_y` — and `immediate=True` deliberately opts out of the
  very deferral Textual documents (`widget.py:3051-3056`) as existing to obtain
  a settled `max_scroll_y`.

Outcome for the user: dragging the scrollbar to the end of the list does not
survive the tick, and the distance jumped grows with list length.

**Intended outcome:** the bottom pin stops being a per-tick snapshot the app
re-applies, and becomes a *mode* Textual's compositor maintains at arrange time
— the one moment the new geometry is final.

## Approach

Replace the hand-rolled bottom pin with Textual's first-class anchor. The
compositor recomputes `new_scroll_y = total_region.bottom - container_height`
inside the arrange pass (`_compositor.py:609`) and writes it with `set_reactive`,
so there is no snapshot, no one-row threshold, no retry budget and no
`immediate=True` race.

Three facts from Textual 8.2.7 make this work without any tolerance heuristic:

| gesture | path | effect on the anchor |
|---|---|---|
| wheel **up** / thumb grab | `_scroll_up_for_pointer` → `_scroll_to(release_anchor=True)`; `ScrollBar._on_mouse_capture` | releases |
| wheel **down** | `_scroll_down_for_pointer(release_anchor=False)` then `watch_scroll_y` → `_check_anchor` | re-arms iff it lands at `max_scroll_y` |
| thumb drag release | `ScrollBar._on_mouse_release` → `parent._check_anchor()` | re-arms iff it landed at `max_scroll_y` |
| `end` key | `scroll_end` → `widget.py:3072` | re-arms explicitly |

So the arming decision is made **by the user's gesture, against live geometry**,
which is exactly what the snapshot could not do.

The mid-list anchor-id + delta path (`pick_scroll_anchor` /
`resolve_anchor_target` / `list_layout_pending` + the retry ladder) is
**unchanged** — it is correct and its tests pass.

### Two hazards the design must guard (both found while tracing, both real)

1. **Spurious re-arm during the rebuild.** `Widget._check_anchor` re-arms when
   `scroll_y >= max_scroll_y`. During `remove_children()` the container is
   childless, so `max_scroll_y == 0` and the clamp has already made
   `scroll_y == 0` — `0 >= 0` is trivially true. Left alone, **every tick would
   silently re-pin a mid-list reader to the bottom.**
2. **Negative offset on a pinned list that stops overflowing.** The compositor's
   *container* branch (`_compositor.py:609`) writes `new_scroll_y` through
   `set_reactive`, which bypasses `validate_scroll_y` — unlike the non-container
   branch at `:693`, which uses the reactive setter and therefore clamps. If
   agents die until the list is shorter than the viewport, `new_scroll_y` goes
   negative and stays negative on every arrange. **Unverified at plan time** —
   pre-phase step 1 decides it.

---

### Pre-phase (risk mitigations)

Both steps run **before** any edit to `.aitask-scripts/monitor/minimonitor_app.py`
and each has a defined effect on the plan below.

1. `[probe_compositor_negative_anchor_offset]` Write a throwaway headless probe
   (scratchpad, not committed): boot an `App` with a `VerticalScroll`, call
   `anchor()`, mount enough `Static`s to overflow, settle, then
   `remove_children()` down to fewer rows than the viewport and settle again.
   Read `scroll_y`, `max_scroll_y` and `virtual_size.height`.
   - **negative `scroll_y` observed** → keep the degenerate-range guard in
     **Step 3** and keep **Step 5 test 6** as a real regression pin.
   - **`scroll_y >= 0`** → Textual clamps somewhere the source read did not
     show. **Drop the guard from Step 3** rather than shipping dead code, and
     turn **Step 5 test 6** into a characterization pin of the clamped behaviour with a
     comment naming this probe. Record the measured numbers either way.

2. `[measure_thumb_drag_arming_live]` Build the live tmux fixture of **Step 6**
   **first, against unchanged `minimonitor_app.py`**, and use it to measure what
   a real SGR thumb drag to the trough end actually produces: log
   `scroll_y`, `max_scroll_y` and `is_anchored` / `_anchor_released` immediately
   after the release, at two list lengths (approx. 20 and approx. 60 agents).
   This doubles as the positive control for the fixture itself — a fixture that
   cannot show the *old* code drifting cannot show the new code holding.
   - **the drag lands at `max_scroll_y`** → the arming design in **Step 1**
     stands unchanged, and **Step 1b below is not implemented at all** (no dead
     code).
   - **the drag reliably stops short** → implement **Step 1b**.
   - Either way, record the measured numbers in the Final Implementation Notes.

### Step 1b — Conditional: app-owned thumb-release seam (only if pre-phase 2 demands it)

**The seam problem, stated first, because it is what makes a naive tolerance
wrong.** `Widget._check_anchor()` takes **no arguments** and is called from two
places that need opposite treatment:

| caller | when | wants tolerance? |
|---|---|---|
| `Widget.watch_scroll_y` (`widget.py:1962`) | after **every** scroll change | **No** — a tolerance here re-pins a user who deliberately parked one or two rows above the bottom, which is exactly the AC3 violation |
| `ScrollBar._on_mouse_release` (`scrollbar.py:374`) | once, at the end of a thumb drag | Yes — a deliberate "I dragged to the end" gesture |

And the obvious ambient discriminator does **not** work: `_on_mouse_release`
executes `self.grabbed = None` on the line **before** `self.parent._check_anchor()`,
so `Widget.is_vertical_scrollbar_grabbed` (`widget.py:2008`) already reads False
by the time `_check_anchor` runs. Nothing in the call gives the source away.

**The seam.** `Widget.vertical_scrollbar` (`widget.py:2036`) is a plain,
overridable `@property`, so the release site can be made an app-owned fact
instead of an inference:

```python
class MiniPaneScrollBar(ScrollBar):
    """The list's own scrollbar, so "a thumb drag just ended" is a state this
    app OWNS rather than one it has to infer. See the table above."""

    def _on_mouse_release(self, event) -> None:
        owner = self.parent if isinstance(self.parent, MiniPaneList) else None
        if owner is not None and self.vertical:
            owner._thumb_release_pending = True
        try:
            super()._on_mouse_release(event)   # calls parent._check_anchor()
        finally:
            if owner is not None and self.vertical:
                owner._thumb_release_pending = False


class MiniPaneList(VerticalScroll):
    _thumb_release_pending = False   # CLASS attr, like the other scroll state

    @property
    def vertical_scrollbar(self) -> ScrollBar:
        # Mirrors Widget.vertical_scrollbar exactly, including the
        # `_start_widget` registration; only the class differs.
        if self._vertical_scrollbar is not None:
            return self._vertical_scrollbar
        self._vertical_scrollbar = bar = MiniPaneScrollBar(
            vertical=True, name="vertical",
            thickness=self.scrollbar_size_vertical,
        )
        bar.display = False
        self.app._start_widget(self, bar)
        return bar

    def _check_anchor(self) -> None:
        if self._locked() or self.max_scroll_y <= 0:
            return
        if self._thumb_release_pending:
            # Tolerance DERIVED from the input device's own quantum, never a
            # constant: one screen row of thumb travel maps to
            # virtual_size / window_size content rows (scrollbar.py:384-392).
            quantum = self.virtual_size.height / max(1, self.container_size.height)
            if self.max_scroll_y - self.scroll_y <= quantum:
                self.scroll_end(animate=False, immediate=True)  # re-arms at :3072
                return
        super()._check_anchor()
```

**Tests that must accompany Step 1b** (they are the reason it is safe):

* `test_thumb_release_snaps_within_one_quantum` — set `_thumb_release_pending`,
  park the list `quantum - 1` rows above the bottom, call `_check_anchor()`,
  assert it armed and landed at `max_scroll_y`.
* `test_thumb_release_does_not_snap_beyond_the_quantum` — same, parked
  `quantum + 2` rows up; assert it did **not** arm. Pins the boundary rather
  than leaving the predicate open-ended.
* `test_watch_scroll_y_never_snaps` — **the AC3 guard.** With
  `_thumb_release_pending` False (its only steady state), scroll to one row
  above the bottom via `_scroll_to` and assert the list stays there across 3
  refresh ticks and `is_bottom_pinned` stays False. Delete the
  `_thumb_release_pending` check from `_check_anchor` and this test must fail.
* `test_the_owned_scrollbar_is_installed` — `isinstance(list.vertical_scrollbar,
  MiniPaneScrollBar)` and the flag is set/cleared around a real
  `ScrollBar._on_mouse_release`. Without this the three tests above could pass
  against a flag nothing ever sets.

**Cost, stated honestly:** Step 1b adds a second private-Textual coupling
(`_on_mouse_release`, `_start_widget`, `_vertical_scrollbar`) on top of the
`_anchor_released` read, which is why it is gated on measurement and not built
speculatively.

---

## Pre-phase results and the amendment they forced (measured 2026-08-31)

**Pre-phase 1 — hazard 2 CONFIRMED.** An anchored `VerticalScroll` that stops
overflowing holds `scroll_y = -8` with `max_scroll_y = 0` (`total_region.bottom`
4 minus container height 12), and recovers to `max_scroll_y` on regrowth. The
Step 3 degenerate-range guard ships, and it must clamp WITHOUT releasing.

**Pre-phase 2 — the approved arming design was FALSIFIED.** The live fixture
works (real pty, real SGR drag, a `grab` event proving the press hits the thumb)
and reproduces the reported bug against unchanged code:

```
tick=  2 y= 20.98 max= 50 GAP= 29.02 vh= 80
tick=  3 y= 40.98 max=130 GAP= 89.02 vh=160
tick= 17 y= 15.98 max=108 GAP= 92.02 vh=138
tick= 20 y=  2.98 max= 70 GAP= 67.02 vh=100
```

Two findings, and the second invalidates the plan as approved:

1. **The one-row `at_bottom` window is not the trigger.** With card-height churn
   SYNCHRONISED to the rebuild, the unchanged code held
   `max_scroll_y - scroll_y == 0` across 15+ consecutive ticks — including a drag
   deliberately stopped one screen row short of the trough end, because the
   7-row thumb absorbs it. The drift appears only once card heights change **out
   of band with the refresh cycle**, which is what production does (gate rows,
   concern rows, marks arriving between ticks). That also explains the
   reporter's "larger on a longer list": the gap tracks the content-height swing.

2. **Textual's anchor would never ARM under those conditions.**
   `Widget._check_anchor` requires `scroll_y >= max_scroll_y`, and when
   `max_scroll_y` moves between 44 and 156 several times a second, no gesture
   lands on it — measured: the drag ended at 20.98 of 50. The plan as approved
   would have shipped and left the reported symptom in place. Step 1b's
   quantum-sized tolerance does not close a 29-row gap either.

**Amendment (user-approved).** Textual's anchor still does the *pinning* — it is
the only thing that recomputes the offset at arrange time. What changes is the
**arming**: "the user is pinned to the bottom" becomes an INTENT recorded at the
gesture, not a position compared against a `max_scroll_y` that is already stale
by the time the comparison runs.

- `MiniPaneList._on_scroll_to` records, **at request time**, whether the thumb
  drag asked for a position at or beyond the then-current `max_scroll_y` — i.e.
  whether it was clamped at the end. That is the geometry the user was actually
  looking at, and it is the only moment the question has a stable answer.
- `MiniPaneScrollBar._on_mouse_release` (the app-owned seam from Step 1b) marks
  the release, and `MiniPaneList._check_anchor` arms on that flag rather than on
  a numeric tolerance. Step 1b's `quantum` predicate is **dropped** — it was
  designed against the wrong root cause.
- The `_locked()` / `max_scroll_y <= 0` refusal stays, but applies only to the
  `watch_scroll_y` path it was written for (the degenerate `0 >= 0` mid-rebuild).
  A real end-of-drag gesture is never refused by it.

## Implementation steps

### Step 1 — `MiniPaneList` (`.aitask-scripts/monitor/minimonitor_app.py:426`)

Three additions; `scroll_to_region` and `_scroll_to` are left exactly as they are.

```python
def on_mount(self) -> None:
    # Arm Textual's first-class bottom anchor ONCE, then release it so the list
    # opens at the top. From here on the arming decision belongs to the user's
    # own gesture: release_anchor() fires on any scroll away and _check_anchor
    # re-arms when a gesture lands at max_scroll_y. `anchor()` calls
    # scroll_end() internally; the container is still empty here, so it is a
    # no-op.
    self.anchor()
    self.release_anchor()

@property
def is_bottom_pinned(self) -> bool:
    """True while Textual's anchor is holding this list at the bottom.

    `is_anchored` is public; the released flag is not. The private read is
    encapsulated HERE and nowhere else, so a Textual rename is one edit
    (`textual>=8.2.7,<9` in aitask_setup.sh floats within major 8).
    """
    return self.is_anchored and not self._anchor_released

def _check_anchor(self) -> None:
    # Hazard 1 above. Refuse while the rebuild lock is held, and refuse a list
    # with nothing to scroll — neither state can be a user gesture.
    if self._locked() or self.max_scroll_y <= 0:
        return
    super()._check_anchor()
```

The compositor's anchored write goes through `set_reactive` and bypasses **both**
existing overrides and `_list_scroll_lock` — and that is the wanted behaviour,
not an oversight: the lock exists to refuse *uninvited* scrolls that would fight
the pending restore, and under this design the compositor's write **is** the
restore. Document that in the `MiniPaneList` class docstring, which currently
claims the two overrides are an exhaustive partition of every scroll.

### Step 2 — `_capture_list_scroll` (`:1552`)

Replace the geometry snapshot with a live mode read. The tuple keeps its shape
(`_pending_scroll_state[0]` is now `pinned`, not `at_bottom`), so the existing
test literals stay valid:

```python
-        max_y = container.max_scroll_y
-        scroll_y = container.scroll_y
-        at_bottom = max_y <= 0 or scroll_y >= max_y - 1
+        scroll_y = container.scroll_y
+        pinned = container.is_bottom_pinned
```

### Step 3 — `_restore_list_scroll` (`:1598`)

The pinned branch returns **before** the readiness gate, so the retry ladder no
longer runs for a pinned list at all:

```python
if pinned:
    # The compositor owns the offset now: it recomputes it from
    # total_region.bottom inside the arrange pass, i.e. at the one moment the
    # new geometry is final. Nothing to restore — only correct the degenerate
    # range (hazard 2) and release the lock.
    if container.max_scroll_y <= 0 and container.scroll_y != 0:
        container.scroll_y = 0      # reactive setter: clamps, does NOT release
    self._pending_scroll_state = None
    self._stop_scroll_lock_timer()
    self.call_after_refresh(self._release_list_scroll_lock, gen)
    return
```

`container.scroll_y = 0` is deliberate: the reactive setter validates and clamps,
and unlike `scroll_to()` it does not call `release_anchor()`, so the pin survives
a shrink and re-engages by itself when the list regrows. **Pre-phase step 1
decides whether these two lines ship at all.**

### Step 4 — Docstrings that now justify themselves with a case that no longer reaches them

* `list_layout_pending` (`:395`) — drop the "for a bottom-pinned list the target
  IS `max_scroll_y`, so `target > max_scroll_y` is vacuously false" half; keep
  the anchored-list half, which still stands. Add the sampling note from the
  side findings below.
* the class-attribute comment on `_pending_scroll_state` (`:589`) — the tuple's
  first element is now `pinned`.
* the module header and `EarlyRestoreCallbackTests` docstring in
  `tests/test_minimonitor_scroll_preservation.py` — both describe the old
  three-part mechanism and the bottom-pin regression.

### Step 5 — `tests/test_minimonitor_bottom_pin.py` (new, headless)

Reuses `_RefreshHost` from `tests/test_minimonitor_scroll_preservation.py` (the
real `MiniMonitorApp` with only its tmux collaborators stubbed) — import it
rather than restating a look-alike host.

1. `test_list_opens_armed_but_released` — `is_anchored` True, `is_bottom_pinned`
   False, `scroll_y == 0` after the first tick.
2. `test_gesture_to_the_bottom_arms_the_pin` — wheel-down to the end;
   `is_bottom_pinned` becomes True. Positive control for every case below.
3. `test_pin_survives_ten_ticks_with_card_height_churn` — **AC1/AC2.** Pin, then
   run ≥10 `_refresh_data()` ticks with panes added/removed *and* card text
   growing/shrinking; assert `max_scroll_y - scroll_y == 0` after **every** tick
   and `max_scroll_y > 0` throughout (a fixture that stops overflowing would
   make it vacuous).
4. `test_user_scroll_away_is_not_repinned` — **AC3.** Scroll up from the bottom,
   run 3 ticks, assert the position holds and `is_bottom_pinned` stays False.
5. `test_rebuild_lock_refuses_the_spurious_rearm` — **hazard 1.** With
   `_list_scroll_lock` True and `max_scroll_y == 0`, call `_check_anchor()` from
   a mid-list position and assert it did **not** arm; then unlock, land a
   gesture at the bottom, and assert it **does** arm, so the refusal is not
   vacuous.
6. `test_pinned_list_that_stops_overflowing_never_goes_negative` — **hazard 2**,
   shaped by pre-phase step 1.

If pre-phase 2 puts **Step 1b** into scope, its four tests
(`test_thumb_release_snaps_within_one_quantum`,
`test_thumb_release_does_not_snap_beyond_the_quantum`,
`test_watch_scroll_y_never_snaps`, `test_the_owned_scrollbar_is_installed`) go
into this same module.

### Step 6 — `tests/test_minimonitor_bottom_pin_live.py` (new, live tmux) — **AC5**

A headless test is explicitly not sufficient evidence: `run_test` settles layout
synchronously, so the restore always ran at `attempt=0` against final geometry
and produced **zero** shortfall at N = 6/12/24/48/96.

#### Fixed geometry — pinned, not assumed

Every dimension the gesture depends on is fixed by the fixture and then
**re-derived from the app itself**, because a hard-coded SGR coordinate that
misses the thumb produces a silent no-op drag that *both* the legacy and the
anchored run would "pass".

```
new-session -d -x 120 -y 40        # deterministic server-side window size
split-window -h -l 40              # minimonitor pane: exactly 40 x 40
set -g mouse off                   # tmux must not interpret; send-keys -l
                                   # writes raw bytes to the pane's tty anyway
```

Following `tests/test_board_startup_focus_live.py`: throwaway per-process socket
(`ait_t1653_pin_$$`), `AITASKS_TMUX_SOCKET` exported into the pane via an `env`
prefix on the command (`tmux set-environment` does not reach a command typed into
an already-running shell), and minimonitor **split beside a second pane** — it
auto-closes when alone in its window. Raw `tmux` is correct here:
`tests/test_no_raw_tmux.sh` scopes its guard to `.aitask-scripts/` and explicitly
exempts `tests/`; the task file's claim that the guard covers test fixtures is
wrong, and the correction goes in the Final Implementation Notes.

Skip only for environment unavailability (no tmux binary, no server, no pane).
Once a pane exists, a lost pin — or a missed gesture — is a **FAILURE**.

#### The harness reports geometry; the test computes the gesture

`tests/lib/minimonitor_live_harness.py` subclasses `_RefreshHost`, drives
`_refresh_data()` on a fast `set_interval`, varies card height per tick, and
writes two artifacts:

* `geometry.json`, written **once** after the list has laid out and overflowed —
  screen-absolute coordinates taken from the compositor
  (`app.screen.find_widget(bar).region`), never guessed:

  ```json
  {"list_region": [x, y, w, h], "scrollbar_region": [x, y, w, h],
   "thumb_top": r, "thumb_size": n, "window_size": ws,
   "window_virtual_size": vs, "max_scroll_y": m}
  ```

* `trace.jsonl`, one line per tick: `{"tick", "scroll_y", "max_scroll_y",
  "is_anchored", "anchor_released"}`, plus a `{"event": "grab"}` line the
  moment `is_vertical_scrollbar_grabbed` first goes True and a
  `{"event": "release"}` line when it goes False again.

The test then derives the gesture from `geometry.json` (SGR is 1-based screen
coords; `region` is 0-based, so add 1):

```
col   = scrollbar_region.x + 1
press = scrollbar_region.y + thumb_top + thumb_size // 2 + 1   # mid-thumb
end   = scrollbar_region.y + window_size                       # trough bottom
```

```bash
tmux send-keys -t "$pane" -l "$(printf '\033[<0;%d;%dM' "$col" "$press")"
tmux send-keys -t "$pane" -l "$(printf '\033[<32;%d;%dM' "$col" "$end")"
tmux send-keys -t "$pane" -l "$(printf '\033[<0;%d;%dm' "$col" "$end")"
```

#### Assertions, in order — each one gates the next

1. **`geometry.json` exists and `max_scroll_y > 0`.** Otherwise the fixture never
   overflowed and everything below is vacuous → FAIL, not skip.
2. **The press hit the thumb.** `trace.jsonl` must contain a `grab` event, then a
   `release`. No `grab` → FAIL with *"the synthesised press missed the thumb"*,
   naming the computed `col`/`press` and the reported `scrollbar_region`. This is
   the assertion the first draft of this plan was missing entirely.
3. **Comparability.** The legacy and anchored runs must report the same
   `geometry.json` (same pane size, same agent count, same `max_scroll_y` at drag
   time). A mismatch is a fixture fault → FAIL, so the two runs are never
   compared across different geometry.
4. **Pre-fix shortfall recorded (negative control).** With
   `AIT_T1653_LEGACY_PIN=1` — the harness subclasses back to the pre-fix
   behaviour (`at_bottom` snapshot + `scroll_end(immediate=True, force=True)`) —
   assert `max_scroll_y - scroll_y > 0` on at least one of 10 post-drag ticks,
   and **record the measured shortfall** in the Final Implementation Notes. If
   the legacy run does *not* drift, the fixture does not reproduce the bug and
   the anchored run proves nothing → FAIL. The replica is test-local and used
   only as a control, so it cannot produce a false PASS of the real path.
5. **AC1/AC2.** With the real code, `max_scroll_y - scroll_y == 0` on **all** 10
   post-drag ticks while card heights churn and agents come and go.

State the boundary explicitly in the module docstring: `main()`'s tmux detection
and config load are *not* exercised — only the app, in a real pty, with real
mouse input.

### Step 7 — Runner registration

The live module boots a real TUI in a tmux pane under a wall-clock budget, so it
joins the serial carve-out. Edit **both**, in the same commit
(`tests/test_serial_carveout_doc_drift.sh` enforces agreement):

* `SERIAL_CARVE_OUT` in `tests/run_all_python_tests.sh`
* the `<!-- serial-carve-out:begin -->` block in `CLAUDE.md`

---

## Decisions the task asked to be recorded

**Retry ladder — keep it.** `_SCROLL_RESTORE_MAX_ATTEMPTS` and both readiness
gates guard the **mid-list** restore, where they are not vacuous: t1539 measured
`list_layout_pending` True on 320 of 488 sampled ticks. The t1653 exploration
measured zero, but an exploration that could not reproduce a state is not
evidence the state cannot occur, and the two measurements contradict each other.
The **bottom** path stops using them entirely, which is the real removal — the
"vacuously false" caveat disappears because the case never reaches the predicate.

**Side finding — lexicographic `window_index` sort** (`monitor_core.py:866` is a
`str`; both `MiniMonitorApp._rebuild_pane_list` and `MonitorApp._rebuild_pane_list`
sort on it, so windows order 1, 10, 11, …, 2, 20) → **split out.** It is a
separate visible defect in a different subsystem, changes agent ordering in
**two** TUIs, and needs its own tests. Recorded as an upstream defect in the
Final Implementation Notes so Step 8b offers it as a follow-up task.

**Side finding — card-only sampling.** `_capture_list_scroll` and
`list_layout_pending` sample only `MiniPaneCard`s while session dividers and the
`other (N)` header also mount → **no behaviour change; documented.** The
predicate is sound on the subset: a divider is a fixed-height `Static` mounted
*before* its group's first card, so it cannot make "every card reports 0" false
while the layout has in fact landed. State this in `list_layout_pending`'s
docstring rather than widening the sample.

## Verification

```bash
# Unit / behavioural
/home/ddt/.aitask/venv/bin/python tests/test_minimonitor_bottom_pin.py
/home/ddt/.aitask/venv/bin/python tests/test_minimonitor_scroll_preservation.py
/home/ddt/.aitask/venv/bin/python tests/test_minimonitor_top_chrome_render.py

# Live acceptance (AC1/AC2/AC5) + its negative control
/home/ddt/.aitask/venv/bin/python tests/test_minimonitor_bottom_pin_live.py

# Guards
bash tests/test_serial_carveout_doc_drift.sh
bash tests/test_no_raw_tmux.sh

# Whole suite (verdict is the LAST line; piping discards the status)
set -o pipefail; bash tests/run_all_python_tests.sh
```

Then, by hand: `ait minimonitor` in a real pane with enough agents to overflow —
drag the thumb to the end of the trough and confirm the list stays at the bottom
across several ticks, and that scrolling away is still honoured.

## Post-implementation

Step 8 review → Step 8b records the lexicographic-sort upstream defect → Step 9
(Post-Implementation) for archival. Work is on the current branch (profile
`fast`, `create_worktree: false`), merge target `main`.

## Risk

### Code-health risk: medium
- The bottom pin is handed to **Textual internals** — the private `_anchor_released` flag and the compositor's anchor block (`_compositor.py:609`) — under a floating pin (`textual>=8.2.7,<9` in `aitask_setup.sh`), so a minor release inside major 8 could rename or reshape either. · severity: medium · → mitigation: inline pre-phase probe_compositor_negative_anchor_offset
- The compositor's *container* branch writes `scroll_y` through `set_reactive`, bypassing `validate_scroll_y` (unlike the non-container branch at `:693`, which clamps). A pinned list that stops overflowing may therefore hold a **negative** offset on every arrange. The guard is designed but the behaviour is **unverified at plan time**. · severity: medium · → mitigation: inline pre-phase probe_compositor_negative_anchor_offset
- **Conditional Step 1b only.** If pre-phase 2 shows a real thumb drag lands short, the fallback owns `MiniPaneList.vertical_scrollbar` and subclasses `ScrollBar._on_mouse_release`, adding a SECOND private-Textual coupling (`_on_mouse_release`, `_start_widget`, `_vertical_scrollbar`) on top of the `_anchor_released` read. It is gated on measurement precisely so it is never built speculatively, and its `test_watch_scroll_y_never_snaps` case is the executable AC3 guard. · severity: medium · → mitigation: inline pre-phase measure_thumb_drag_arming_live
- `_check_anchor` is a private-method override, so the fix is behaviourally coupled to Textual's two call sites for it (`watch_scroll_y`, `ScrollBar._on_mouse_release`). Blast radius is otherwise small: one file, one widget class and two app methods, with the whole existing t1539 suite retained. · severity: low · → mitigation: None (accepted; pinned by the Step 5 suite)

### Goal-achievement risk: low
*Reassessed after the inline pre-phases were confirmed: both bullets below are
now decided by measurement BEFORE the design is committed, and each has a
specified fallback, so neither can silently carry the implementation to a wrong
outcome. The pre-fix baseline run in pre-phase step 2 also falsifies a
third-cause reading if one exists. Code-health stays medium: the private-API
coupling to Textual under a floating `<9` pin is not addressed by either probe.*
- **Arming depends on the user's gesture landing at exactly `max_scroll_y`** — `Widget._check_anchor` has no tolerance. The task's own measurement says one screen row of thumb travel maps to `virtual_size / window_size` content rows (2.87 in the fixture), so a drag that stops one screen row short of the trough end never satisfies the predicate, the pin never arms, and the reported symptom survives the fix. Only a live thumb drag can decide this, and the fallback is now a DEFINED, app-owned seam (Step 1b) rather than an aspiration — `_check_anchor` receives no source information and `ScrollBar.grabbed` is cleared before it is called, so the discrimination had to be owned locally by overriding the `vertical_scrollbar` property. · severity: high · → mitigation: inline pre-phase measure_thumb_drag_arming_live
- **Diagnosis divergence.** The task attributes the failure to the one-row `at_bottom` window; the same trace equally supports "the restore fired against a `max_scroll_y` that was not yet final" (max swings 67 → 73 → 88 *within* a tick). The anchor fixes both readings, but if the true cause is a third thing the change is inert. · severity: medium · → mitigation: inline pre-phase measure_thumb_drag_arming_live

### Planned mitigations
- timing: pre-phase | name: probe_compositor_negative_anchor_offset | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 2 (compositor set_reactive bypasses validate_scroll_y) | desc: Headless probe measuring whether an anchored VerticalScroll that stops overflowing really holds a negative scroll_y, so the degenerate-range guard ships only if it is needed.
- timing: pre-phase | name: measure_thumb_drag_arming_live | type: test | priority: high | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement risk 1 (arming needs the gesture to land exactly at max_scroll_y) | desc: Build the live tmux fixture first against unchanged code and measure what a real SGR thumb drag produces, deciding whether the arming design stands or whether the fully specified, app-owned Step 1b drag-release seam ships.


---

# Implementation record (deviations from the approved plan)

The two pre-phases did what they were for: one confirmed a hazard, the other
falsified the approved arming design, and a third finding during implementation
falsified my first correction of it. Recorded here in the order it happened,
because the order is the evidence.

## 1. The compositor's unclamped write is real, and a one-shot correction loses

Pre-phase 1 measured `scroll_y = -8` at `max_scroll_y = 0` on a bare anchored
`VerticalScroll` that stopped overflowing (`total_region.bottom` 4 minus
container height 12), recovering to `max_scroll_y` on regrowth.

**Deviation:** the plan's Step 3 clamped it inline in `_restore_list_scroll`.
That does not work — the compositor reasserts the value on EVERY arrange, so a
correction applied before the arrange is simply overwritten, and one applied from
a post-refresh callback was measured being rewritten to -2 by the next layout.
The shipped fix is `MiniPaneList._reconcile_anchor`, which **suspends** Textual's
anchor while the range is degenerate and re-engages it when content regrows,
keeping the user's request in `_pin_suspended` across the suspension. It runs
from the app's post-rebuild callback and from `on_resize` (a pane resize
re-arranges with no rebuild at all).

## 2. Arming cannot be a position comparison — but not for the reason the task gave

The live fixture reproduces the reported bug against unchanged code. Getting it
to do so took four corrections, each a real fault:

| symptom | cause |
|---|---|
| app ran at 80x24 in a 40x40 pane | `split-window` had stdout redirected to a file, so Textual had no tty size and no SIGWINCH |
| `virtual_h == container_h`, no overflow | with the task/gate caches stubbed a card renders ONE row, so 30 cards exactly filled a 30-row container |
| geometry never published | it was sampled straight after `await _refresh_data()`, i.e. mid-rebuild, where `max_scroll_y` is 0 |
| control reported a zero gap | the control undid only the app's capture/restore; `_anchored` was still set, so the compositor pinned it anyway and the comparison was vacuous |

With those fixed, the control drifts exactly as reported — the view sticks and
never returns to the bottom, the gap growing to 146 rows as content grows.

**The task's stated trigger did not reproduce.** With card-height churn
synchronised to the rebuild, the unchanged code held `max_scroll_y - scroll_y == 0`
across 15+ ticks, including a drag deliberately stopped one screen row short of
the trough end (the 7-row thumb absorbs it). The drift needs card heights to
change **out of band with the refresh tick**, which is what production does. That
is also what makes the gap grow with list length — the reporter's "larger on a
longer list".

**Deviation:** Step 1b was approved with a `quantum`-sized tolerance. That is not
what shipped, and the quantum idea was wrong. What ships records, at REQUEST
time, whether the drag asked to go at or past the end of the thumb's travel
(`_on_scroll_to`), and arms on that at the release (`MiniPaneScrollBar`
+ `_check_anchor`).

## 3. The intent seam was removed and then restored — on evidence both times

Deleting it left every headless test AND two live runs passing, so it was removed
as unproven complexity. The next live run failed with `scroll_y = 43.745` frozen
against a `max_scroll_y` of 50: Textual's re-arm fires mid-drag *sometimes*,
purely on timing, and when it does not the list drifts for the rest of the
session. The seam went back in with that measurement attached.

A further 1-in-8 flake then showed the comparison itself was wrong: the drag's
`y` is computed by `ScrollBar._on_mouse_move` from the SCROLLBAR's
`window_virtual_size / window_size`, so comparing it against the CONTAINER's
`max_scroll_y` mixes two clocks and scores a genuine drag-to-the-end as short.
The comparison now happens in the scrollbar's own coordinate space.

## 4. What the headless tests can and cannot prove

Stated in `tests/test_minimonitor_bottom_pin.py`'s docstring rather than left
implicit, because two of the plan's four negative controls were measured PASSING
against the fix: headlessly `App.run_test` settles layout synchronously, a drag
always lands exactly on `max_scroll_y`, and Textual re-arms on its own. The
capture-mode change and the whole arming mechanism are pinned only by the live
module. The rebuild-lock guard and the degenerate-range suspension are pinned
headlessly and both controls were confirmed failing.

## 5. Fixture reliability is part of the deliverable

`test_3b_the_gesture_actually_scrolled_the_list` exists because a gesture that
does not land leaves the list exactly where it was, which is indistinguishable in
the trace from a lost pin. Adding it turned an unexplained 1-in-10 "the fix
failed" into an explicit "the fixture failed", and then into a diagnosis:

| fixture fault | measured | fix |
|---|---|---|
| a single motion event lands mid-rebuild and is dropped outright — `Widget._on_scroll_to` gates on `_allow_scroll`, which on a `VerticalScroll` tracks `show_vertical_scrollbar`, False while the container is childless | 5 failures / 12 runs | send a STREAM of motion events, as a real drag does; whichever lands outside the rebuild window counts |
| the press row was scaled by `thumb_size`, which the churn moves between 5 and 19 rows, so aiming at the middle of a 19-row thumb missed a 5-row one | 1 failure / 12 runs, on the grab | offset from `thumb_top` (0 while `scroll_y` is 0, which the test asserts) rather than from the size |
| the gesture's own samples counted as steady state | — | the observation window starts at the RELEASE, so the discard count does not have to track the gesture's length |
| pressing row 0 grabs but often does not scroll | 5 of 12 moved | avoid row 0; press one row below the thumb's top |
| the app came up 80x24 inside a 40x40 pane, so every coordinate computed from the pane was wrong | 1 failure in the first full-suite run; then 6 errors, DETERMINISTICALLY, under `pytest` | `env -u COLUMNS -u LINES` on the pane command. Rich honours `COLUMNS`/`LINES` over the real pty size, pytest exports them for its own terminal writer, and the tmux server inherits the environment of the client that started it. My standalone runs used `python tests/…` (unittest) and never saw it; the suite runs pytest, which always does. |

The first diagnosis of that last one was wrong and worth recording: I read "80x24"
as Textual's no-tty fallback and added a repeating `resize-pane` nudge to force a
SIGWINCH. It did nothing — 45s of nudging left the app at 80 columns — because
stdout WAS a tty the whole time. Adding `app_size` / `stdout_isatty` / `term` /
`columns_env` to the geometry the harness publishes turned a guess into a
one-line answer, and the nudge was removed rather than left in as insurance for a
cause that did not exist. `await_geometry` still waits for geometry matching the
pane, because that wait is what caught it.

Each is recorded in the test's own comments so the next person does not
"simplify" it back. Rate after all four: 15 consecutive clean runs, against a
5-in-12 baseline when the fixture was first written.

## 6. Step 4's docstring sweep, completed at review

Caught in review: `tests/test_minimonitor_scroll_preservation.py` still explained
itself with the old mechanism, and its `EarlyRestoreCallbackTests` docstring
still named the bottom path as "the one that regressed" via a readiness test that
"compared `max_scroll_y` against itself". That case now passes for a completely
different reason — `_restore_list_scroll` returns before the gate for a pinned
list — so the text would have sent the next person investigating the retry ladder
in the wrong direction. Step 4 of this plan required the update and it had only
been done for the production file.

Corrected: the module header now says the anchor-id path, the readiness gate and
the retry ladder all belong to the MID-LIST restore, points at the two new
modules for the bottom pin, and notes that the tuple literals passing `False`
select the mid-list path deliberately now that the field is `pinned`. The class
docstring separates the two cases, and
`test_bottom_pin_survives_an_early_restore_callback` is relabelled a
characterization pin with its own docstring explaining that `scroll_end` arms the
anchor and the compositor is what holds the offset.

## 7. Unchanged from the plan

The retry ladder is kept (the bottom path simply no longer reaches it), the
lexicographic `window_index` sort is split out as an upstream defect, and the
card-only sampling of `list_layout_pending` is documented rather than widened.
The task file's claim that `tests/test_no_raw_tmux.sh` forces the live fixture
through the tmux gateway is wrong — that guard scopes itself to
`.aitask-scripts/` and explicitly exempts `tests/`.


## Final Implementation Notes

- **Actual work done:** minimonitor's bottom-of-list pin moved from a per-tick
  geometry snapshot to Textual's own anchor, with the app owning the ARMING.
  `MiniPaneList` gains `on_mount` (arm then release, so the list opens at the top
  but `_anchored` is true), `is_bottom_pinned`, a `release_anchor` override,
  `_reconcile_anchor`, `on_resize`, `_on_scroll_to`, `_check_anchor`, and an
  owned `vertical_scrollbar` returning the new `MiniPaneScrollBar`.
  `_capture_list_scroll` records the live mode instead of measuring geometry and
  `_restore_list_scroll` returns before the readiness gate for a pinned list.
  New: `tests/test_minimonitor_bottom_pin.py` (8),
  `tests/test_minimonitor_bottom_pin_live.py` (6) and
  `tests/lib/minimonitor_live_harness.py`; the live module joins
  `SERIAL_CARVE_OUT` and CLAUDE.md's marker block (both count pins bumped 3 → 4).
  Docs: the bottom pin and scrollbar drag are described in
  `website/content/docs/tuis/minimonitor/how-to.md`.

- **Deviations from plan:** three, each forced by a measurement and each recorded
  in full above. (1) The approved arming design — Textual's own
  `scroll_y >= max_scroll_y` — was falsified: under out-of-band content churn no
  gesture lands on a moving `max_scroll_y`, so arming became intent-based via an
  app-owned drag-release seam, and Step 1b's `quantum` tolerance was dropped as
  the wrong answer to the wrong root cause. (2) Step 3's inline degenerate-range
  clamp does not work — the compositor reasserts the value on every arrange — so
  the anchor is suspended for the duration instead (`_reconcile_anchor`).
  (3) A docs change was added; it was not in the plan, but the behaviour is
  user-visible.

- **Issues encountered:** the task file's stated trigger did not reproduce — with
  churn synchronised to the rebuild the pre-fix code held the pin across 15+
  ticks, including a drag stopped a screen row short. The drift requires card
  heights changing OUT OF BAND with the tick. Building a fixture that shows this
  took six corrections, five of them caught by the two non-vacuity assertions
  (`grab`, "the gesture actually scrolled"); the last, `COLUMNS=80` inherited
  from pytest through the tmux server, made the app render 80x24 inside a 40x40
  pane and was only findable after the harness started publishing
  `stdout_isatty` / `app_size` / `columns_env`. My first diagnosis of it (a
  missed SIGWINCH) was wrong and the `resize-pane` nudge built on it was removed
  rather than kept as insurance.

- **Key decisions:** the retry ladder and both readiness gates are KEPT — they
  guard the mid-list restore, where t1539 measured them firing on 320 of 488
  ticks; only the bottom path stops reaching them. Two of the plan's four
  negative controls are documented as NOT discriminating (headlessly or live),
  rather than left to look like coverage. The intent seam was removed and then
  restored, both times on measurement.

- **Upstream defects identified:**
  - `monitor/monitor_core.py:866 — PaneSnapshot.window_index is a str, so both
    MiniMonitorApp._rebuild_pane_list and MonitorApp._rebuild_pane_list sort
    agents lexicographically (1, 10, 11, …, 2, 20) instead of numerically.
    Affects agent ordering in two TUIs; needs its own tests.`
  - `tests/test_parallel_admission_purity.py — unrelated to this task; it and the
    roadmap_* files were modified by a concurrent session (t1569_5) and are
    deliberately NOT part of this commit.`
