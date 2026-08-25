---
priority: high
effort: high
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitormini, aitask_monitor, tui, tmux, performance]
gates: [risk_evaluated]
created_at: 2026-08-25 10:54
updated_at: 2026-08-25 10:54
---

## Problem

When `ait minimonitor` spawns as a companion pane beside a freshly launched code
agent, the TUI is **unresponsive to input for ~10 seconds** after boot. The agent
list is rendered and a card is highlighted, but clicking a row does nothing and
the focused agent cannot be changed. After the stall it behaves normally.

The symptom is **startup-only** — it never recurs on later refresh ticks.

## Root cause (verified by measurement)

Three things compose. Only the first is a trigger; the second is the structural
amplifier that turns it into dead input.

### 1. The first refresh tick unconditionally runs the prioritized-marks purge

`.aitask-scripts/monitor/monitor_shared.py:352` seeds
`self._marks_purge_due_at = 0.0` — the comment states the intent outright: *"0.0
⇒ the first refresh tick after mount materializes a purge."*

`_maybe_purge_marks` (`monitor_shared.py:625`) therefore fires on tick 1 and
`await`s a subprocess at `monitor_shared.py:647`:
`aitask_agent_marks.sh purge --observed <file>`.

### 2. That subprocess blocks for its full lock timeout on a wedged global mutex

`aitask_agent_marks.sh:111` acquires via `marks_lock_or_busy 10`
(`PURGE_LOCK_TIMEOUT=10`, `aitask_agent_marks.sh:58`).
`registry_lock.sh:91-121` spins to the deadline and returns `LOCK_BUSY`.

The lock is not merely contended — it is **permanently wedged**, and
`registry_lock.sh:59-66` documents exactly this failure mode ("wedges that one
lock: every later acquire reports busy with no holder in existence. The cure is
manual").

Observed on the reporting machine:

```
$ cat ~/.config/aitasks/agent_marks.json.lockd/pid
3733146                      # dead process, dir stamped 2026-08-23 16:30

$ ls -d ~/.config/aitasks/agent_marks.json.lockd.gc
.../agent_marks.json.lockd.gc          # the reclaim guard dir EXISTS

$ time ./.aitask-scripts/aitask_agent_marks.sh list
LOCK_BUSY
real    0m10.267s
```

`.aitask-scripts/lib/stale_lock.sh:251` reclaims a dead-pid lock **only after
`mkdir "$gc"` succeeds**. With the `.gc` guard dir already present, `mkdir`
always fails, so reclaim can never run and every acquire burns its full timeout
forever.

### 3. The first refresh runs on the App message pump, so the `await` eats input

`.aitask-scripts/monitor/minimonitor_app.py:1163` dispatches the first tick with
`self.call_later(self._refresh_data)`.

In Textual 8.2.7, `call_later` posts an `events.Callback` to the App's own queue,
and `MessagePump.on_callback` does `await invoke(event.callback)` **inline in the
App's message-processing loop** (`textual/message_pump.py:890-900`). Key and
mouse events are dispatched by `App.on_event` from that **same serialized
queue**. So for the entire duration of the first `_refresh_data`, every click and
keypress sits queued — while the Screen's own pump keeps painting.

This is why the symptom is startup-only: ticks 2+ come from the interval timer,
which runs its callback in its **own task** (`textual/timer.py:91`
`create_task(self._run_timer())`), so their awaits do not block input dispatch.

### Why the symptom looks the way it does

Ordering inside `_refresh_data` (`minimonitor_app.py:1183`):

| line | what happens |
|---|---|
| 1255 | `await _rebuild_pane_list()` — **the agent list becomes visible** |
| 1257 | `_restore_focus(...)` — **a card is highlighted** |
| 1263 | `await _maybe_offer_concerns()` — shadow settling work |
| 1267 | `await _maybe_purge_marks()` — **the ~10 s stall** |

Rendered, focused, and dead to input — exactly as reported.

### Why "in parallel to a code agent" makes it worse

Tick 1 has no tmux control client yet (it is still connecting), so every tmux
round-trip is a real fork/exec — roughly **33 process spawns in the first tick**
against a single-threaded tmux server that is simultaneously busy rendering the
code agent that just launched. Each `capture-pane` carries a 5 s timeout and the
`asyncio.gather` is only as fast as the slowest pane.

## Secondary defects found in the same path

These are latent today but each can independently reproduce a smaller (or
larger) version of the stall. They should be fixed with the primary cause, not
deferred, because #2 above makes every one of them user-visible.

1. **Blocking `start_control_client` on a coroutine worker.**
   `minimonitor_app.py:1157-1162` calls
   `self.run_worker(_connect_control_client(), ...)` with a **coroutine**, not
   `thread=True`, so Textual runs it on the event loop. Its body
   (`monitor_core.py:1539`) is `async def` with a **fully synchronous body**:
   `TmuxControlBackend.start()` (`monitor_core.py:1221`) does
   `threading.Event.wait(timeout=2.0)` (`:1236`) then
   `concurrent.futures.Future.result(timeout=5.0)` (`:1248`); on failure it calls
   `stop()` (`:1347`) which blocks a further 1.0 + 3.0
   (`_BACKEND_STOP_TIMEOUT`) + 3.0 (`_BACKEND_THREAD_JOIN_TIMEOUT`).
   Measured at **53 ms** on a healthy box, but the worst case is ~14 s of hard-
   blocked event loop — which would freeze *painting* too, not just input.

2. **Sync tmux round-trips still on minimonitor's refresh path.** The full
   monitor was already hardened against these; minimonitor never got the fix:
   - `minimonitor_app.py:1201` `get_session_to_project_mapping()` (sync;
     `monitor_core.py:1798`) — `monitor_app.py:978` uses the `_async` variant
   - `minimonitor_app.py:1219` `_update_own_window_info()` (sync `tmux_run`)
   - `minimonitor_app.py:1223` `_check_auto_close()` → `discover_window_panes`
     → sync `tmux_run` at the default 5 s
   - `monitor_core.py:3181` shadow phase re-stamp (sync `set-option -p`)

   Note `request_sync` blocks for `timeout + 1.0` (`monitor_core.py:1420`), so
   the worst case here is roughly 3+3+6+6 s of blocked loop per tick.

3. **A subprocess spawned for a hidden widget.** `_rebuild_session_bar`
   (`minimonitor_app.py:1611`) calls `_get_desync_summary` at `:1632`, which
   spawns a Python interpreter (`monitor/desync_summary.py:44-50`, 2 s cap).
   `bar.display = self._session_bar_enabled` is only set afterwards at `:1651`,
   and `session_bar` defaults to **`False`** (`minimonitor_app.py:4335`) — so on
   a default install this cost is paid every 30 s for output nobody sees.

## Parallel surface — `ait monitor` has the identical pattern

Fix both in the same change:

- `monitor_app.py:821` `self.call_later(self._refresh_data)` (the pump dispatch)
- `monitor_app.py:1072` `await self._maybe_purge_marks()` (the tick-1 purge)
- `monitor_app.py:808/814` the same coroutine-worker `start_control_client`

`monitor_shared.py:352` is shared by both apps, so the purge-scheduling fix lands
once and covers both.

## Test gap

`tests/test_monitor_refresh_no_sync_tmux.py` guards the full monitor's refresh
path against sync tmux calls, but **never instantiates `MiniMonitorApp`**
(verified: zero matches for `MiniMonitorApp` / `minimonitor` in that file). That
is precisely why the sync round-trips above survived in minimonitor only.

There is also **no live boot / time-to-interactive test for minimonitor**,
unlike `tests/test_board_startup_focus_live.py` and
`tests/test_codebrowser_startup_focus_live.py`.

Note that a plain asyncio event-loop lag probe **does not detect this bug** — it
measured zero stalls >150 ms during a real boot, because the App pump is
serialized independently of loop responsiveness. Any regression test must assert
on **input dispatch latency** (a queued key/click actually being handled), not on
loop lag.

## Suggested direction

Ordered by what actually removes the symptom:

1. **Do not schedule the marks purge on tick 1.** Seed
   `_marks_purge_due_at = time.monotonic() + <grace>` at `monitor_shared.py:352`,
   and/or dispatch it fire-and-forget (`run_worker(..., thread=True)`) rather
   than `await`ing it inside `_refresh_data`. The purge only bounds store growth
   — the render path already filters expired marks every tick — so it has no
   reason to be on the critical path at all.
2. **Get the first refresh off the App pump** (`set_timer(0, ...)` or an explicit
   worker), so a slow tick can never queue input. Move the trailing maintenance
   at `:1263` and `:1267` out of the render callback entirely.
3. **Fix the wedged-lock recovery gap** in `stale_lock.sh:251`: a `.gc` guard dir
   whose own creator is long gone must itself be reclaimable, otherwise a single
   crash at the wrong instant disables the mutex permanently with no automatic
   cure. (Immediate manual workaround for the reporting machine:
   `rmdir ~/.config/aitasks/agent_marks.json.lockd.gc` and remove
   `~/.config/aitasks/agent_marks.json.lockd`.)
4. Make `start_control_client` genuinely async (`await asyncio.to_thread(backend.start)`)
   or launch the worker with `thread=True`.
5. Port minimonitor's `_refresh_data` to the async gateway variants and extend
   `tests/test_monitor_refresh_no_sync_tmux.py` to cover `MiniMonitorApp`.
6. Move the `_get_desync_summary` call below the `bar.display` check.

## Acceptance criteria

- With the `agent_marks` lock artificially wedged (dead-pid lock dir + `.gc`
  guard present), a freshly booted minimonitor dispatches a key/click within a
  small bounded budget (well under 1 s) instead of ~10 s.
- The marks purge still runs — it is deferred, not deleted — and its recurrence
  interval (`_MARKS_PURGE_INTERVAL`) is unchanged.
- A wedged lock whose guard-dir creator is dead is recoverable without manual
  intervention.
- `tests/test_monitor_refresh_no_sync_tmux.py` (or a sibling) covers
  `MiniMonitorApp` and fails on any sync tmux call left on its refresh path.
- A regression test asserts on **input-dispatch latency**, not event-loop lag.
- `ait monitor` receives the same fixes; no surface keeps the old pattern.

## Notes

- Read `aidocs/framework/tui_conventions.md` and
  `aidocs/framework/tmux_gateway.md` before touching these paths.
- `aidocs/framework/testing_conventions.md` covers the `App.run_test` /
  `@work`-worker interaction that a boot test here will run into.
