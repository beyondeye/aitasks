---
Task: t2050_minimonitor_width_pin_reads_stale_size.md
Base branch: main
Output branch: main
---

# Plan: minimonitor width pin reads a stale size (t2050)

## Context

The minimonitor re-pins its tmux pane to `tmux.minimonitor.width` (default 40) on resize
(t978: `MiniMonitorApp.on_resize` → `_maybe_pin_width`,
`.aitask-scripts/monitor/minimonitor_app.py:1483` / `:1535`). It decides from
`self.size.width`, but in Textual 8.2.7 a subclass's public `on_resize` runs **before**
`App._on_resize` (`textual/app.py:4345`) stores `event.size`. So `self.size` is still
the PREVIOUS size, and the pin never fires on growth. Seen in practice: `ait ide`
restores frozen agents into detached 80-column windows (39 | 40 split). On first view
those windows grow to 270, and the companions stay ~135 wide.

Outcome: the pin reads the new size, so t978's "correct only when wider" rule works
again. That covers restored windows, any growth, and drags wider.

## Scope decisions

- **Kept: "correct only when wider"**, unchanged from t978. A pane narrower than the
  target is left alone, whether it got there by a window shrink or a drag.
- **Deferred: shrink restoration.** Telling a window shrink from a border drag needs
  a cause signal the app does not have: a pane that a window resize leaves untouched
  gets no SIGWINCH. The tmux-hook route found in planning brings inheritance and
  lifetime machinery. It goes to a follow-up task that records the probe findings
  (created after this task is committed).
- **`ait ide` restore-before-attach: no change.** With the pin working, a restored
  window corrects itself on first view (Resize 135 > 40 → pin).
- **No new tmux calls, and none on the mount path.** The fix only changes which
  width the existing handler reads.

## Implementation

1. **`.aitask-scripts/monitor/minimonitor_app.py`**
   - `on_resize`: call `self._maybe_pin_width(event.size.width)`. Add a short comment
     on why `self.size` must not be read here: Textual's handler order leaves
     `App._size` stale inside a subclass `on_resize`.
   - `_maybe_pin_width(self, width: int)`: the same guards as today; the test becomes
     `if width <= self._target_width: return`. The docstring says what `width` is
     and keeps the self-termination argument (the follow-up Resize at the target
     returns early).
   - Budget comment at `:208-212`: no change; "only shrinks a pane that is wider than
     it" is still accurate.

2. **`tests/test_minimonitor_width_pin.py`** (new, unittest, Textual pilot). The host
   is the real `MiniMonitorApp` with `TMUX` scrubbed, so `on_mount` takes its "Not
   inside tmux" early return. This is the `_ListHost` pattern from
   `tests/test_minimonitor_scroll_preservation.py`. `TMUX_PANE` is patched to `%9`,
   and after boot `_monitor` is a fake that records `resize_pane` calls. The tests
   drive the real event path with `pilot.resize_terminal`, so `self.size` really is
   stale inside the handler:
   - grow 40→55 → exactly one `resize_pane("%9", x=40)`. This fails on pre-fix code,
     which makes zero calls.
   - the 80→270-shaped jump 40→135 → `resize_pane(x=40)`.
   - resize to exactly 40 → no call; narrow 40→20 → no call (behaviour preserved).
   - no `TMUX_PANE`, or `_monitor is None` → no call.

3. **`tests/lib/minimonitor_width_pin_harness.py`** plus
   **`tests/test_minimonitor_width_pin_live.py`** (new). Isolation follows
   `tests/test_minimonitor_bottom_pin_live.py`:
   - an `ait_t2050_<cur|leg>_<pid>` socket;
   - `AITASKS_TMUX_SOCKET` and `-u COLUMNS -u LINES` in the pane env;
   - stdout kept on the tty;
   - `kill-server` on exit;
   - skip only when tmux or the venv python is missing; a missed budget fails.

   The harness subclasses `mm.MiniMonitorApp`, with `TMUX` popped and `TMUX_PANE`
   kept, so the real `on_mount` returns early. After mount it sets
   `self._monitor = TmuxMonitor(session=...)`, the real gateway `resize_pane` on the
   isolated socket. It writes a `ready` event and traces each `_maybe_pin_width`
   call. `AIT_T2050_LEGACY_PIN=1` overrides `_maybe_pin_width` with the pre-fix body
   (reads `self.size.width`). That override is a test-local negative control only;
   overriding `on_resize` would not suppress the parent handler, because Textual runs
   every class's handler in the MRO.

   Scenario, which is the restored-window case:
   - `new-session -d -x 80 -y 24` → `split-window -h -l 40 <harness>` → wait for
     ready;
   - `resize-window -x 270`, standing in for the first client view;
   - **fixed run**: poll until `#{pane_width}` == 40;
   - **legacy run**: assert it stays ≥ 80 for the whole settle window, reproducing the
     reported ~135.

   The docstring states the boundary: `main()`/config and the frozen-restore
   coordinator are not exercised, and `resize-window` stands in for a client attach.

4. **Serial carve-out.**
   - Add `test_minimonitor_width_pin_live.py` to `SERIAL_CARVE_OUT` in
     `tests/run_all_python_tests.sh`, with a rationale comment.
   - Add it to the CLAUDE.md `serial-carve-out` block, and update the prose to "the
     other four stay off it — two boot their own synthetic projects, and the two
     minimonitor modules drive an app whose data sources are stubbed, twice per run
     (the fix and its pre-fix control)".
   - `tests/test_serial_carveout_doc_drift.sh` guards the pair.

5. **Follow-up task (post-commit, not in this diff)**: "minimonitor: restore the
   target width after a window shrink". Its body records:
   - the no-SIGWINCH-for-untouched-panes finding;
   - the window-scoped `window-resized` hook probe results;
   - the two hazards: a local array shadows `-gw` global hooks even when emptied, and
     the hook must be bound to the live instance (`pane_pid` plus the
     `@aitask_monitor_kind` marker), with a whole-name unset on exit.

## Verification

- Run `~/.aitask/venv/bin/python tests/test_minimonitor_width_pin.py` and
  `~/.aitask/venv/bin/python tests/test_minimonitor_width_pin_live.py`. The fixed run
  must pass, and the legacy control must show the stale width.
- Positive control by hand, on a scratch copy and never `git restore`: put
  `self.size.width` back in the pin. The grow pilot tests and the live fixed run must
  fail.
- Neighbours: `tests/test_minimonitor_scroll_preservation.py`,
  `tests/test_minimonitor_startup_input_latency.py`,
  `tests/test_minimonitor_bottom_pin_live.py`, `bash tests/test_no_raw_tmux.sh`,
  `bash tests/test_serial_carveout_doc_drift.sh`.
- Full suite: `set -o pipefail; bash tests/run_all_python_tests.sh`, reading the last
  line.
- Step 9 (Post-Implementation): `ait gates run`, then archival.

## Risk

### Code-health risk: low
- One handler argument changes, with no new tmux calls or state. The new live module
  adds suite wall-clock; it is carved out of the parallel pool and uses polled
  deadlines · severity: low · → mitigation: none

### Goal-achievement risk: low
- The live test stands in for the first client view with `resize-window` on a
  detached session. Both go through tmux's layout resize, and the legacy control
  proves the fixture reproduces the ~135 drift. Shrink restoration is deliberately
  out of scope (deferred to the follow-up) · severity: low · → mitigation: none
