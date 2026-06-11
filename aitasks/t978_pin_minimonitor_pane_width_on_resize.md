---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tmux, monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-11 13:06
updated_at: 2026-06-11 13:07
---

## Problem

The `minimonitor` companion pane (the narrow ~40-column side column spawned
next to an agent pane) grows much wider than its intended fixed width after the
terminal is resized — in particular the detach -> resize terminal -> reattach
sequence. Observed: a window like `agent-pick-891_4` ended up with a
minimonitor companion pane of very large width. The expectation is that
minimonitor keeps a fixed/standard width and never grows above it.

## Root cause

The width is set **only once, at spawn time**. In
`.aitask-scripts/lib/agent_launch_utils.py::maybe_spawn_minimonitor()` the pane
is created with:

```
split_argv = ["split-window", "-h", "-P", "-F", "#{pane_id}", "-l", str(width)]
```

(`width = 40` default at `:670`, overridable via `tmux.minimonitor.width` in
`project_config.yaml` at `:686-687`). The `-l 40` sizes the new pane to 40
columns **at that instant only**. tmux then stores the window layout as
**proportions**, not as a fixed column count. When the terminal is later
resized (especially while detached, then reattached at a different size), tmux's
layout engine rescales every pane proportionally to fill the new width — so the
40-of-N-columns pane becomes the same *fraction* of the now-wider terminal, far
exceeding 40 columns.

Confirmed there is **no mechanism that re-pins the width after spawn**:
- No `resize-pane` calls anywhere in `.aitask-scripts/`.
- No tmux hooks for `client-resized` / `window-layout-changed`.
- `.aitask-scripts/monitor/minimonitor_app.py` has no width handling: its CSS
  (`:79-136`) uses `1fr`/`auto` and adapts to whatever pane width tmux gives it;
  it never asks tmux to re-pin its own pane geometry, even though it already
  knows its own pane via `$TMUX_PANE` and re-queries window info each refresh.

So minimonitor *was* designed as a fixed ~40-col side column, but "fixed" was
only enforced at creation and tmux's proportional resize silently overrides it.

## Goal

Make the minimonitor companion pane re-pin itself to its configured width when
the terminal/pane is resized (including detach -> reattach), so it never grows
above the standard width.

## Approach (route the resize through the t952 gateway)

Per repo direction (task **t952**, Done — centralize tmux invocations behind the
shared `TmuxClient` gateway in `.aitask-scripts/lib/tmux_exec.py`), the new
`resize-pane` command must be a gateway method, NOT an inline `tmux resize-pane`
call.

1. **Gateway (`tmux_exec.py::TmuxClient`):** add a typed
   `resize_pane(pane, *, x=None, y=None)` method (the sole place the
   `resize-pane` verb is spawned, alongside the existing `session_target` /
   `window_target` helpers). It owns socket flag + targeting like the rest of
   the gateway.

2. **Re-pin on resize (`minimonitor_app.py`):** handle Textual's `on_resize`
   event and, when the pane width exceeds the configured target, clamp it by
   calling the gateway (via `self._monitor.tmux_run([...])` or the new
   `resize_pane`) with `-x <width>` on `$TMUX_PANE`. This fires on
   detach->reattach as well, defeating tmux's proportional rescale. Guard
   against resize-feedback loops (only resize when actually wider than target;
   tolerate the case where the app is not the companion pane).

3. **Plumb the width into the app:** `minimonitor_app.py::main()` currently does
   NOT read `tmux.minimonitor.width` (only the spawner does) — read it via the
   existing `_load_project_tmux_config` path and pass it to `MiniMonitorApp`
   (default 40) so the app knows its clamp target.

## Notes / cross-references

- t952 (Done) — tmux command gateway (`tmux_exec.py` / `TmuxClient`); the
  resize command belongs here. See its plan `aiplans/archived/p952...`.
- Spawn site: `agent_launch_utils.py::maybe_spawn_minimonitor()` (`:634-759`),
  width at `:670` / `:686-687`, split at `:743-744`.
- minimonitor app: `.aitask-scripts/monitor/minimonitor_app.py` (CSS `:79-136`,
  config load `_load_project_tmux_config` `:1041`, `main()` `:1055`).
- Config knob: `tmux.minimonitor.width` (documented in
  `website/content/docs/tuis/minimonitor/how-to.md:155-162`; NOT in
  `seed/project_config.yaml` — consider documenting there too).
- Read `aidocs/framework/tui_conventions.md` (Textual TUI / tmux pane spawning)
  before implementing.
- Consider whether the same proportional-rescale issue affects the
  minimonitor's tmux pane in multi-pane windows generally; scope this fix to the
  companion-pane width but note the general behavior.
