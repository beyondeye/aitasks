---
priority: low
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [aitask_monitormini, tui, tmux]
followup_kind: carry_over
created_at: 2026-10-18 16:59
updated_at: 2026-10-18 16:59
---

## Context

Deferred from t2050. That task fixed the minimonitor width pin's stale-size read: `on_resize` now passes `event.size.width` to `_maybe_pin_width` (`.aitask-scripts/monitor/minimonitor_app.py`). It also kept t978's rule unchanged: **correct only when wider**. A companion that ends up NARROWER than `tmux.minimonitor.width` is left alone. One way that happens is a window shrink: in a 270→200 probe the companion went 40 → 5, and nothing restores it.

This task decides whether, and how, to restore the target width after a **window** shrink. A border drag that narrows the pane should keep being respected.

## What t2050's planning established (probed in isolated tmux 3.8 servers)

1. **The app cannot tell the cause from its own Resize events.** tmux sends SIGWINCH only to panes whose size changed. Growing a 270-col window to 271 can leave a 40-col companion untouched, so the app never hears about it. Any "window width changed since my last Resize" record therefore misreads a later border drag as a window change. App-side history is unreliable by construction.
2. **A window-scoped `window-resized` hook does see every window resize, and a border drag never fires it.** Probe results:
   - shrink, grow, and control-client-driven growth all fire it;
   - `resize-pane` does not fire it.
   This is the viable cause signal. Two hazards make it non-trivial, so it was cut from t2050's scope:
   - **Inherited hooks are silenced.** `set-hook -g window-resized …` lands in the global window options (`show-hooks -gw`). ANY window-local `window-resized` array shadows it, even with a different index. An array emptied with `set-hook -wu 'window-resized[N]'` still shadows (a bare `window-resized` line remains). Only `set-hook -wu window-resized`, unsetting the whole name, removes the shadow. Installing must therefore decline when no local array exists and the global one has entries. Cleanup must unset the whole name when ours was the only entry.
   - **Lifetime.** A guard that only checks the window id stays active after the minimonitor exits to a surviving shell, and it forces that shell back to 40. Binding the guard to the live instance works in the probe. The binding is `#{pane_pid}` plus the app's own `@aitask_monitor_kind = minimonitor:<pid>` marker (stamped in `on_mount`, cleared in `on_unmount`), inside an `if-shell -F -t <pane> '#{&&:…}' 'resize-pane …'`. A normal exit, a `respawn-pane`, and moving the pane to another window all make it inert. Residue: a hard kill of a minimonitor started from an interactive shell leaves the binding active, because formats cannot test pid liveness.
   - Any install or cleanup tmux call must stay off the mount/exit critical path (t1622 — `tests/test_minimonitor_startup_input_latency.py` pins it). Use an async `run_worker` and the ambient `TmuxClient(socket_args=[])`, as `_seed_own_window_info` does.
3. Precedent for not clobbering other hooks: `attach_companion_cleanup_hook`'s `pane-died` slot policy in `.aitask-scripts/lib/agent_launch_utils.py`.

## Decide first

Is the shrink case worth the persistent tmux state? Alternatives worth weighing:
- leave it as is (narrow stays narrow until the user drags or the window grows past the target, at which point the t978 pin takes over);
- the hook design above;
- some cheaper signal not yet found.

## Tests if implemented

Live tmux tests on an isolated socket, following `tests/test_minimonitor_width_pin_live.py`:
- shrink restore;
- the exact 270 → 271 → drag-to-20 sequence (the drag must be kept);
- a planted global `window-resized` hook that must still fire;
- a minimonitor exit with the pane surviving (no forced width afterwards);
- `respawn-pane`.
